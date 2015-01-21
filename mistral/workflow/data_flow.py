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
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral import utils
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def prepare_db_task(task_db, task_spec, upstream_task_specs, exec_db,
                    cause_task_db=None):
    """Prepare Data Flow properties ('in_context' and 'input')
     of given DB task.

    :param task_db: DB task to prepare.
    :param task_spec: Task specification.
    :param upstream_task_specs: Specifications of workflow upstream tasks.
    :param exec_db: Execution DB model.
    """

    upstream_db_tasks = wf_utils.find_db_tasks(
        exec_db,
        upstream_task_specs
    )

    task_db.in_context = utils.merge_dicts(
        copy.copy(exec_db.context),
        _evaluate_upstream_context(upstream_db_tasks)
    )

    if cause_task_db:
        # TODO(nmakhotkin): Do it using _evaluate_upstream_context()
        # TODO(rakhmerov): Think if Data Flow should be a part of wf handler.
        task_db.in_context = utils.merge_dicts(
            task_db.in_context,
            evaluate_outbound_context(cause_task_db)
        )

    task_db.input = evaluate_task_input(
        task_spec,
        task_db.in_context
    )


def evaluate_task_input(task_spec, context):
    with_items = task_spec.get_with_items()

    # Do not evaluate input in case of with-items task.
    # Instead of it, input is considered as data defined in with-items.
    if with_items:
        return expr.evaluate_recursively(with_items, context or {})
    else:
        return expr.evaluate_recursively(task_spec.get_input(), context)


def _evaluate_upstream_context(upstream_db_tasks):
    ctx = {}

    for t_db in upstream_db_tasks:
        utils.merge_dicts(ctx, evaluate_outbound_context(t_db))

    return ctx


def evaluate_task_output(task_db, task_spec, raw_result):
    """Evaluates task output given a raw task result from action/workflow.

    :param task_db: DB task
    :param task_spec: Task specification
    :param raw_result: Raw task result that comes from action/workflow
        (before publisher). Instance of mistral.workflow.base.TaskResult
    :return: Complete task output that goes to Data Flow context.
    """
    publish_dict = task_spec.get_publish()

    # Combine the raw result with the environment variables as the context
    # for evaulating the 'publish' clause.
    out_context = copy.deepcopy(raw_result.data) or {}
    if (task_db.in_context and '__env' in task_db.in_context and
            isinstance(out_context, dict)):
        out_context['__env'] = task_db.in_context['__env']
    output = expr.evaluate_recursively(publish_dict, out_context) or {}

    # Add same result to task output under key 'task'.
    output['task'] = {
        task_spec.get_name(): copy.copy(output) or raw_result.error
    }

    return output


def evaluate_workflow_output(wf_spec, context):
    """Evaluates workflow output.

    :param wf_spec: Workflow specification.
    :param context: Final Data Flow context (cause task's outbound context).
    """
    output_dict = wf_spec.get_output()

    # Evaluate 'publish' clause using raw result as a context.
    output = expr.evaluate_recursively(output_dict, context)

    return output or context


def evaluate_outbound_context(task_db):
    """Evaluates task outbound Data Flow context.

    This method assumes that complete task output (after publisher etc.)
    has already been evaluated.
    :param task_db: DB task.
    :return: Outbound task Data Flow context.
    """

    in_context = copy.deepcopy(dict(task_db.in_context)) \
        if task_db.in_context is not None else {}

    return utils.merge_dicts(
        in_context,
        task_db.output
    )


def add_openstack_data_to_context(context):
    if context is None:
        context = {}

    if CONF.pecan.auth_enable:
        exec_ctx = auth_ctx.ctx()

        LOG.debug('Data flow security context: %s' % exec_ctx)

        if exec_ctx:
            context.update({'openstack': exec_ctx.to_dict()})

    return context


def add_execution_to_context(exec_db, context):
    if context is None:
        context = {}

    context['__execution'] = {
        'id': exec_db.id,
        'wf_spec': exec_db['wf_spec'],
        'start_params': exec_db.start_params,
        'input': exec_db.input
    }

    return context


def add_environment_to_context(exec_db, context):
    if context is None:
        context = {}

    # If env variables are provided, add an evaluated copy into the context.
    if 'environment' in exec_db.start_params:
        env = copy.deepcopy(exec_db.start_params['environment'])
        # An env variable can be an expression of other env variables.
        context['__env'] = expr.evaluate_recursively(env, {'__env': env})

    return context
