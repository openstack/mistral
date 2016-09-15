# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import copy

from oslo_config import cfg
from oslo_log import log as logging

from mistral import context as auth_ctx
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral import utils
from mistral.utils import inspect_utils
from mistral.workbook import parser as spec_parser
from mistral.workflow import states
from mistral.workflow import with_items

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class ContextView(dict):
    """Workflow context view.

    It's essentially an immutable composite structure providing fast lookup
    over multiple dictionaries w/o having to merge those dictionaries every
    time. The lookup algorithm simply iterates over provided dictionaries
    one by one and returns a value taken from the first dictionary where
    the provided key exists. This means that these dictionaries must be
    provided in the order of decreasing priorities.

    Note: Although this class extends built-in 'dict' it shouldn't be
    considered a normal dictionary because it may not implement all
    methods and account for all corner cases. It's only a read-only view.
    """

    def __init__(self, *dicts):
        super(ContextView, self).__init__()

        self.dicts = dicts or []

    def __getitem__(self, key):
        for d in self.dicts:
            if key in d:
                return d[key]

        raise KeyError(key)

    def get(self, key, default=None):
        for d in self.dicts:
            if key in d:
                return d[key]

        return default

    def __contains__(self, key):
        return any(key in d for d in self.dicts)

    def keys(self):
        keys = set()

        for d in self.dicts:
            keys.update(d.keys())

        return keys

    def items(self):
        return [(k, self[k]) for k in self.keys()]

    def values(self):
        return [self[k] for k in self.keys()]

    def iteritems(self):
        # NOTE: This is for compatibility with Python 2.7
        # YAQL converts output objects after they are evaluated
        # to basic types and it uses six.iteritems() internally
        # which calls d.items() in case of Python 2.7 and d.iteritems()
        # for Python 2.7
        return iter(self.items())

    def iterkeys(self):
        # NOTE: This is for compatibility with Python 2.7
        # See the comment for iteritems().
        return iter(self.keys())

    def itervalues(self):
        # NOTE: This is for compatibility with Python 2.7
        # See the comment for iteritems().
        return iter(self.values())

    def __len__(self):
        return len(self.keys())

    @staticmethod
    def _raise_immutable_error():
        raise exc.MistralError('Context view is immutable.')

    def __setitem__(self, key, value):
        self._raise_immutable_error()

    def update(self, E=None, **F):
        self._raise_immutable_error()

    def clear(self):
        self._raise_immutable_error()

    def pop(self, k, d=None):
        self._raise_immutable_error()

    def popitem(self):
        self._raise_immutable_error()

    def __delitem__(self, key):
        self._raise_immutable_error()


def evaluate_upstream_context(upstream_task_execs):
    published_vars = {}
    ctx = {}

    for t_ex in upstream_task_execs:
        # TODO(rakhmerov): These two merges look confusing. So it's a
        # temporary solution. There's still the bug
        # https://bugs.launchpad.net/mistral/+bug/1424461 that needs to be
        # fixed using context variable versioning.
        published_vars = utils.merge_dicts(
            published_vars,
            t_ex.published
        )

        utils.merge_dicts(ctx, evaluate_task_outbound_context(t_ex))

    return utils.merge_dicts(ctx, published_vars)


def _extract_execution_result(ex):
    if isinstance(ex, models.WorkflowExecution):
        return ex.output

    if ex.output:
        return ex.output['result']


def invalidate_task_execution_result(task_ex):
    for ex in task_ex.executions:
        ex.accepted = False


def get_task_execution_result(task_ex):
    execs = task_ex.executions
    execs.sort(
        key=lambda x: x.runtime_context.get('index')
    )

    results = [
        _extract_execution_result(ex)
        for ex in execs
        if hasattr(ex, 'output') and ex.accepted
    ]

    task_spec = spec_parser.get_task_spec(task_ex.spec)

    if task_spec.get_with_items():
        if with_items.get_count(task_ex) > 0:
            return results
        else:
            return []

    return results[0] if len(results) == 1 else results


def publish_variables(task_ex, task_spec):
    if task_ex.state != states.SUCCESS:
        return

    wf_ex = task_ex.workflow_execution

    expr_ctx = ContextView(
        task_ex.in_context,
        wf_ex.context,
        wf_ex.input
    )

    if task_ex.name in expr_ctx:
        LOG.warning(
            'Shadowing context variable with task name while publishing: %s' %
            task_ex.name
        )

    task_ex.published = expr.evaluate_recursively(
        task_spec.get_publish(),
        expr_ctx
    )


def evaluate_task_outbound_context(task_ex):
    """Evaluates task outbound Data Flow context.

    This method assumes that complete task output (after publisher etc.)
    has already been evaluated.
    :param task_ex: DB task.
    :return: Outbound task Data Flow context.
    """
    in_context = (
        copy.deepcopy(dict(task_ex.in_context))
        if task_ex.in_context is not None else {}
    )

    return utils.update_dict(in_context, task_ex.published)


def evaluate_workflow_output(wf_ex, wf_spec, ctx):
    """Evaluates workflow output.

    :param wf_ex: Workflow execution.
    :param wf_spec: Workflow specification.
    :param ctx: Final Data Flow context (cause task's outbound context).
    """

    output_dict = wf_spec.get_output()

    # Evaluate workflow 'output' clause using the final workflow context.
    ctx_view = ContextView(ctx, wf_ex.context, wf_ex.input)

    output = expr.evaluate_recursively(output_dict, ctx_view)

    # TODO(rakhmerov): Many don't like that we return the whole context
    # if 'output' is not explicitly defined.
    return output or ctx


def add_current_task_to_context(ctx, task_id, task_name):
    ctx['__task_execution'] = {
        'id': task_id,
        'name': task_name
    }

    return ctx


def add_openstack_data_to_context(wf_ex):
    wf_ex.context = wf_ex.context or {}

    if CONF.pecan.auth_enable:
        exec_ctx = auth_ctx.ctx()

        LOG.debug('Data flow security context: %s' % exec_ctx)

        if exec_ctx:
            wf_ex.context.update({'openstack': exec_ctx.to_dict()})


def add_execution_to_context(wf_ex):
    wf_ex.context = wf_ex.context or {}

    wf_ex.context['__execution'] = {
        'id': wf_ex.id
    }


def add_environment_to_context(wf_ex):
    # TODO(rakhmerov): This is redundant, we can always get env from WF params
    wf_ex.context = wf_ex.context or {}

    # If env variables are provided, add an evaluated copy into the context.
    if 'env' in wf_ex.params:
        env = copy.deepcopy(wf_ex.params['env'])

        # An env variable can be an expression of other env variables.
        wf_ex.context['__env'] = expr.evaluate_recursively(env, {'__env': env})


def add_workflow_variables_to_context(wf_ex, wf_spec):
    wf_ex.context = wf_ex.context or {}

    # The context for calculating workflow variables is workflow input
    # and other data already stored in workflow initial context.
    ctx_view = ContextView(wf_ex.context, wf_ex.input)

    wf_vars = expr.evaluate_recursively(wf_spec.get_vars(), ctx_view)

    utils.merge_dicts(wf_ex.context, wf_vars)


def evaluate_object_fields(obj, context):
    fields = inspect_utils.get_public_fields(obj)

    evaluated_fields = expr.evaluate_recursively(fields, context)

    for k, v in evaluated_fields.items():
        setattr(obj, k, v)
