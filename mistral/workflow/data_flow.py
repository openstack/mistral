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

from oslo.config import cfg

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral import utils
from mistral.utils import inspect_utils
from mistral.workflow import states


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def evaluate_upstream_context(upstream_task_execs):
    published_vars = {}
    ctx = {}

    for t_ex in upstream_task_execs:
        # TODO(rakhmerov): These two merges look confusing. So it's a
        # temporary solution.There's still the bug
        # https://bugs.launchpad.net/mistral/+bug/1424461 that needs to be
        # fixed using context variable versioning.
        published_vars = utils.merge_dicts(
            published_vars,
            t_ex.published
        )

        utils.merge_dicts(
            ctx,
            evaluate_task_outbound_context(t_ex, include_result=False)
        )

    ctx = utils.merge_dicts(ctx, published_vars)

    # TODO(rakhmerov): IMO, this method shouldn't deal with these task ids or
    # anything else related to task proxies. Need to refactor.
    return utils.merge_dicts(
        ctx,
        _get_task_identifiers_dict(upstream_task_execs)
    )


# TODO(rakhmerov): Think how to gt rid of this method and the whole trick
# with upstream tasks. It doesn't look clear from design standpoint.
def _get_task_identifiers_dict(task_execs):
    tasks = {}

    for task_ex in task_execs:
        tasks[task_ex.id] = task_ex.name

    return {"__tasks": tasks}


def _extract_execution_result(ex):
    if isinstance(ex, models.WorkflowExecution):
        return ex.output

    if ex.output:
        return ex.output['result']


def get_task_execution_result(task_ex):
    action_execs = task_ex.executions
    action_execs.sort(
        key=lambda x: x.runtime_context.get('with_items_index')
    )

    results = [
        _extract_execution_result(ex)
        for ex in task_ex.executions
        if hasattr(ex, 'output') and ex.accepted
    ]

    if results:
        return results if len(results) > 1 else results[0]
    else:
        return []


class TaskResultProxy(object):
    def __init__(self, task_id):
        self.task_id = task_id

    def get(self):
        task_ex = db_api.get_task_execution(self.task_id)
        return get_task_execution_result(task_ex)

    def __str__(self):
        return "%s [task_id = '%s']" % (self.__class__.__name__, self.task_id)

    def __repr__(self):
        return self.__str__()


class ProxyAwareDict(dict):
    def __getitem__(self, item):
        val = super(ProxyAwareDict, self).__getitem__(item)
        if isinstance(val, TaskResultProxy):
            return val.get()

        return val

    def get(self, k, d=None):
        try:
            return self.__getitem__(k)
        except KeyError:
            return d

    def iteritems(self):
        for k, _ in super(ProxyAwareDict, self).iteritems():
            yield k, self[k]

    def to_builtin_dict(self):
        return {k: self[k] for k, _ in self.iteritems()}


def publish_variables(task_ex, task_spec):
    expr_ctx = extract_task_result_proxies_to_context(task_ex.in_context)

    if task_ex.name in expr_ctx:
        LOG.warning(
            'Shadowing context variable with task name while publishing: %s' %
            task_ex.name
        )

    # Add result of current task to context for variables evaluation.
    expr_ctx[task_ex.name] = TaskResultProxy(task_ex.id)

    task_ex.published = expr.evaluate_recursively(
        task_spec.get_publish(),
        expr_ctx
    )


def destroy_task_result(task_ex):
    for ex in task_ex.executions:
        if hasattr(ex, 'output'):
            ex.output = {}


def evaluate_task_outbound_context(task_ex, include_result=True):
    """Evaluates task outbound Data Flow context.

    This method assumes that complete task output (after publisher etc.)
    has already been evaluated.
    :param task_ex: DB task.
    :param include_result: boolean argument, if True - include the
        TaskResultProxy in outbound context under <task_name> key.
    :return: Outbound task Data Flow context.
    """

    if task_ex.state != states.SUCCESS:
        return task_ex.in_context

    in_context = (copy.deepcopy(dict(task_ex.in_context))
                  if task_ex.in_context is not None else {})

    out_ctx = utils.merge_dicts(in_context, task_ex.published)

    # Add task output under key 'taskName'.
    if include_result:
        task_ex_result = TaskResultProxy(task_ex.id)

        out_ctx = utils.merge_dicts(
            out_ctx,
            {task_ex.name: task_ex_result or None}
        )

    return ProxyAwareDict(out_ctx)


def evaluate_workflow_output(wf_spec, context):
    """Evaluates workflow output.

    :param wf_spec: Workflow specification.
    :param context: Final Data Flow context (cause task's outbound context).
    """
    # Convert context to ProxyAwareDict for correct output evaluation.
    context = ProxyAwareDict(copy.deepcopy(context))

    output_dict = wf_spec.get_output()

    # Evaluate workflow 'publish' clause using the final workflow context.
    output = expr.evaluate_recursively(output_dict, context)

    # TODO(rakhmerov): Many don't like that we return the whole context
    # TODO(rakhmerov): if 'output' is not explicitly defined.
    return ProxyAwareDict(output or context).to_builtin_dict()


def add_openstack_data_to_context(context):
    if context is None:
        context = {}

    if CONF.pecan.auth_enable:
        exec_ctx = auth_ctx.ctx()

        LOG.debug('Data flow security context: %s' % exec_ctx)

        if exec_ctx:
            context.update({'openstack': exec_ctx.to_dict()})

    return context


def add_execution_to_context(wf_ex, context):
    if context is None:
        context = {}

    context['__execution'] = {
        'id': wf_ex.id,
        'spec': wf_ex.spec,
        'params': wf_ex.params,
        'input': wf_ex.input
    }

    return context


def add_environment_to_context(wf_ex, context):
    if context is None:
        context = {}

    # If env variables are provided, add an evaluated copy into the context.
    if 'env' in wf_ex.params:
        env = copy.deepcopy(wf_ex.params['env'])
        # An env variable can be an expression of other env variables.
        context['__env'] = expr.evaluate_recursively(env, {'__env': env})

    return context


# TODO(rakhmerov): Think how to get rid of this method. It should not be
# exposed in API.
def extract_task_result_proxies_to_context(ctx):
    ctx = ProxyAwareDict(copy.deepcopy(ctx))

    for task_ex_id, task_ex_name in ctx['__tasks'].iteritems():
        ctx[task_ex_name] = TaskResultProxy(task_ex_id)

    return ctx


def evaluate_object_fields(obj, context):
    fields = inspect_utils.get_public_fields(obj)

    evaluated_fields = expr.evaluate_recursively(fields, context)

    for k, v in evaluated_fields.items():
        setattr(obj, k, v)
