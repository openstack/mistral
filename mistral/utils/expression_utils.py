# Copyright 2015 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from functools import partial
import warnings

from oslo_log import log as logging
from oslo_serialization import jsonutils
from stevedore import extension
import yaml
import yaql

from mistral.db.v2 import api as db_api
from mistral import utils


LOG = logging.getLogger(__name__)
ROOT_YAQL_CONTEXT = None


def get_yaql_context(data_context):
    global ROOT_YAQL_CONTEXT

    if not ROOT_YAQL_CONTEXT:
        ROOT_YAQL_CONTEXT = yaql.create_context()

        _register_yaql_functions(ROOT_YAQL_CONTEXT)

    new_ctx = ROOT_YAQL_CONTEXT.create_child_context()
    new_ctx['$'] = data_context

    if isinstance(data_context, dict):
        new_ctx['__env'] = data_context.get('__env')
        new_ctx['__execution'] = data_context.get('__execution')
        new_ctx['__task_execution'] = data_context.get('__task_execution')

    return new_ctx


def get_jinja_context(data_context):
    new_ctx = {
        '_': data_context
    }

    _register_jinja_functions(new_ctx)

    if isinstance(data_context, dict):
        new_ctx['__env'] = data_context.get('__env')
        new_ctx['__execution'] = data_context.get('__execution')
        new_ctx['__task_execution'] = data_context.get('__task_execution')

    return new_ctx


def get_custom_functions():
    """Get custom functions

    Retrieves the list of custom evaluation functions
    """
    functions = dict()

    mgr = extension.ExtensionManager(
        namespace='mistral.expression.functions',
        invoke_on_load=False
    )

    for name in mgr.names():
        functions[name] = mgr[name].plugin

    return functions


def _register_yaql_functions(yaql_ctx):
    functions = get_custom_functions()

    for name in functions:
        yaql_ctx.register_function(functions[name], name=name)


def _register_jinja_functions(jinja_ctx):
    functions = get_custom_functions()

    for name in functions:
        jinja_ctx[name] = partial(functions[name], jinja_ctx['_'])


# Additional YAQL functions needed by Mistral.
# If a function name ends with underscore then it doesn't need to pass
# the name of the function when context registers it.

def env_(context):
    return context['__env']


def executions_(context,
                id=None,
                root_execution_id=None,
                state=None,
                from_time=None,
                to_time=None
                ):

    filter = {}

    if id is not None:
        filter = utils.filter_utils.create_or_update_filter(
            'id',
            id,
            "eq",
            filter
        )

    if root_execution_id is not None:
        filter = utils.filter_utils.create_or_update_filter(
            'root_execution_id',
            root_execution_id,
            "eq",
            filter
        )

    if state is not None:
        filter = utils.filter_utils.create_or_update_filter(
            'state',
            state,
            "eq",
            filter
        )

    if from_time is not None:
        filter = utils.filter_utils.create_or_update_filter(
            'created_at',
            from_time,
            "gte",
            filter
        )

    if to_time is not None:
        filter = utils.filter_utils.create_or_update_filter(
            'created_at',
            to_time,
            "lt",
            filter
        )

    return db_api.get_workflow_executions(**filter)


def execution_(context):
    wf_ex = db_api.get_workflow_execution(context['__execution']['id'])

    return {
        'id': wf_ex.id,
        'name': wf_ex.name,
        'spec': wf_ex.spec,
        'input': wf_ex.input,
        'params': wf_ex.params,
        'created_at': wf_ex.created_at.isoformat(' '),
        'updated_at': wf_ex.updated_at.isoformat(' ')
    }


def json_pp_(context, data=None):
    warnings.warn(
        "json_pp was deprecated in Queens and will be removed in the S cycle. "
        "The json_dump expression function can be used for outputting JSON",
        DeprecationWarning
    )
    return jsonutils.dumps(
        data or context,
        indent=4
    ).replace("\\n", "\n").replace(" \n", "\n")


def json_dump_(context, data):
    return jsonutils.dumps(data, indent=4)


def yaml_dump_(context, data):
    return yaml.safe_dump(data, default_flow_style=False)


def task_(context, task_name=None):
    # This section may not exist in a context if it's calculated not in
    # task scope.
    cur_task = context['__task_execution']

    # 1. If task_name is empty it's 'task()' use case, we need to get the
    # current task.
    # 2. if task_name is not empty but it's equal to the current task name
    # we need to take exactly the current instance of this task. Otherwise
    # there may be ambiguity if there are many tasks with this name.
    # 3. In other case we just find a task in DB by the given name.
    if cur_task and (not task_name or cur_task['name'] == task_name):
        task_ex = db_api.get_task_execution(cur_task['id'])
    else:
        task_execs = db_api.get_task_executions(
            workflow_execution_id=context['__execution']['id'],
            name=task_name
        )

        # TODO(rakhmerov): Account for multiple executions (i.e. in case of
        # cycles).
        task_ex = task_execs[-1] if len(task_execs) > 0 else None

    if not task_ex:
        LOG.warning(
            "Task '%s' not found by the task() expression function",
            task_name
        )
        return None

    # We don't use to_dict() db model method because not all fields
    # make sense for user.
    return _convert_to_user_model(task_ex)


def _should_pass_filter(t, state, flat):
    # Start from assuming all is true, check only if needed.
    state_match = True
    flat_match = True

    if state:
        state_match = t['state'] == state

    if flat:
        is_action = t['type'] == utils.ACTION_TASK_TYPE

        if not is_action:
            nested_execs = db_api.get_workflow_executions(
                task_execution_id=t.id
            )

            for n in nested_execs:
                flat_match = flat_match and n.state != t.state

    return state_match and flat_match


def _get_tasks_from_db(workflow_execution_id=None, recursive=False, state=None,
                       flat=False):
    task_execs = []
    nested_task_exs = []

    kwargs = {}

    if workflow_execution_id:
        kwargs['workflow_execution_id'] = workflow_execution_id

    # We can't add state to query if we want to filter by workflow_execution_id
    # recursively. There might be a workflow_execution in one state with a
    # nested workflow execution that has a task in the desired state until we
    # have an optimization for queering all workflow executions under a given
    # top level workflow execution, this is the way to go.
    if state and not (workflow_execution_id and recursive):
        kwargs['state'] = state

    task_execs.extend(db_api.get_task_executions(**kwargs))

    # If it is not recursive no need to check nested workflows.
    # If there is no workflow execution id, we already have all we need, and
    # doing more queries will just create duplication in the results.
    if recursive and workflow_execution_id:
        for t in task_execs:
            if t.type == utils.WORKFLOW_TASK_TYPE:
                # Get nested workflow execution that matches the task.
                nested_workflow_executions = db_api.get_workflow_executions(
                    task_execution_id=t.id
                )

                # There might be zero nested executions.
                for nested_workflow_execution in nested_workflow_executions:
                    nested_task_exs.extend(
                        _get_tasks_from_db(
                            nested_workflow_execution.id,
                            recursive,
                            state,
                            flat
                        )
                    )

    if state or flat:
        # Filter by state and flat.
        task_execs = [
            t for t in task_execs if _should_pass_filter(t, state, flat)
        ]

    # The nested tasks were already filtered, since this is a recursion.
    task_execs.extend(nested_task_exs)

    return task_execs


def tasks_(context, workflow_execution_id=None, recursive=False, state=None,
           flat=False):
    task_execs = _get_tasks_from_db(
        workflow_execution_id,
        recursive,
        state,
        flat
    )

    # Convert task_execs to user model and return.
    return [_convert_to_user_model(t) for t in task_execs]


def _convert_to_user_model(task_ex):
    # Importing data_flow in order to break cycle dependency between modules.
    from mistral.workflow import data_flow

    # We don't use to_dict() db model method because not all fields
    # make sense for user.
    return {
        'id': task_ex.id,
        'name': task_ex.name,
        'spec': task_ex.spec,
        'state': task_ex.state,
        'state_info': task_ex.state_info,
        'result': data_flow.get_task_execution_result(task_ex),
        'published': task_ex.published,
        'type': task_ex.type,
        'workflow_execution_id': task_ex.workflow_execution_id,
        'created_at': task_ex.created_at.isoformat(' '),
        'updated_at': task_ex.updated_at.isoformat(' ')
        if task_ex.updated_at is not None else None
    }


def uuid_(context=None):
    return utils.generate_unicode_uuid()


def global_(context, var_name):
    wf_ex = db_api.get_workflow_execution(context['__execution']['id'])

    return wf_ex.context.get(var_name)


def json_parse_(context, data):
    return jsonutils.loads(data)


def yaml_parse_(context, data):
    return yaml.safe_load(data)
