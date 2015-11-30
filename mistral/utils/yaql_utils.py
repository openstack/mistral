# Copyright 2015 - Mirantis, Inc.
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


import yaql

from mistral.db.v2 import api as db_api
from mistral.workflow import utils as wf_utils
from oslo_serialization import jsonutils
ROOT_CONTEXT = None


def get_yaql_context(data_context):
    global ROOT_CONTEXT

    if not ROOT_CONTEXT:
        ROOT_CONTEXT = yaql.create_context()

        _register_functions(ROOT_CONTEXT)

    new_ctx = ROOT_CONTEXT.create_child_context()
    new_ctx['$'] = data_context

    if isinstance(data_context, dict):
        new_ctx['__env'] = data_context.get('__env')
        new_ctx['__execution'] = data_context.get('__execution')

    return new_ctx


def _register_functions(yaql_ctx):
    yaql_ctx.register_function(env_)
    yaql_ctx.register_function(execution_)
    yaql_ctx.register_function(task_)
    yaql_ctx.register_function(json_pp_, name='json_pp')


# Additional YAQL functions needed by Mistral.
# If a function name ends with underscore then it doesn't need to pass
# the name of the function when context registers it.

def env_(context):
    return context['__env']


def execution_(context):
    return context['__execution']


def json_pp_(data):
    return jsonutils.dumps(
        data,
        indent=4
    ).replace("\\n", "\n").replace(" \n", "\n")


def task_(context, task_name):
    # Importing data_flow in order to break cycle dependency between modules.
    from mistral.workflow import data_flow

    wf_ex = db_api.get_workflow_execution(context['__execution']['id'])

    task_execs = wf_utils.find_task_executions_by_name(wf_ex, task_name)

    # TODO(rakhmerov): Account for multiple executions (i.e. in case of
    # cycles).
    task_ex = task_execs[-1] if len(task_execs) > 0 else None

    if not task_ex:
        raise ValueError(
            'Failed to find task execution with name: %s' % task_name
        )

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
