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

from oslo_serialization import jsonutils
from stevedore import extension
import yaql

from mistral.db.v2 import api as db_api
from mistral import utils


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

    Retreives the list of custom evaluation functions
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


def execution_(context):
    wf_ex = db_api.get_workflow_execution(context['__execution']['id'])

    return {
        'id': wf_ex.id,
        'name': wf_ex.name,
        'spec': wf_ex.spec,
        'input': wf_ex.input,
        'params': wf_ex.params
    }


def json_pp_(context, data=None):
    return jsonutils.dumps(
        data or context,
        indent=4
    ).replace("\\n", "\n").replace(" \n", "\n")


def task_(context, task_name):
    # Importing data_flow in order to break cycle dependency between modules.
    from mistral.workflow import data_flow

    # This section may not exist in a context if it's calculated not in
    # task scope.
    cur_task = context['__task_execution']

    if cur_task and cur_task['name'] == task_name:
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
        return None

    # We don't use to_dict() db model method because not all fields
    # make sense for user.
    return {
        'id': task_ex.id,
        'name': task_ex.name,
        'spec': task_ex.spec,
        'state': task_ex.state,
        'state_info': task_ex.state_info,
        'result': data_flow.get_task_execution_result(task_ex),
        'published': task_ex.published
    }


def uuid_(context=None):
    return utils.generate_unicode_uuid()
