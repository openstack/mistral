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

from oslo_log import log as logging
from osprofiler import profiler
import traceback as tb

from mistral.db.v2.sqlalchemy import models
from mistral.engine import actions
from mistral.engine import task_handler
from mistral import exceptions as exc
from mistral.workbook import parser as spec_parser


LOG = logging.getLogger(__name__)


@profiler.trace('action-handler-on-action-complete')
def on_action_complete(action_ex, result):
    task_ex = action_ex.task_execution

    action = _build_action(action_ex)

    try:
        action.complete(result)
    except exc.MistralException as e:
        msg = ("Failed to complete action [action=%s, task=%s]: %s\n%s" %
               (action_ex.name, task_ex.name, e, tb.format_exc()))

        LOG.error(msg)

        action.fail(msg)

        if task_ex:
            task_handler.fail_task(task_ex, msg)

        return

    if task_ex:
        task_handler.schedule_on_action_complete(action_ex)


@profiler.trace('action-handler-build-action')
def _build_action(action_ex):
    if isinstance(action_ex, models.WorkflowExecution):
        return actions.WorkflowAction(None, action_ex=action_ex)

    wf_name = None
    wf_spec_name = None

    if action_ex.workflow_name:
        wf_name = action_ex.workflow_name
        wf_spec = spec_parser.get_workflow_spec_by_execution_id(
            action_ex.task_execution.workflow_execution_id
        )
        wf_spec_name = wf_spec.get_name()

    adhoc_action_name = action_ex.runtime_context.get('adhoc_action_name')

    if adhoc_action_name:
        action_def = actions.resolve_action_definition(
            adhoc_action_name,
            wf_name,
            wf_spec_name
        )

        return actions.AdHocAction(action_def, action_ex=action_ex)

    action_def = actions.resolve_action_definition(
        action_ex.name,
        wf_name,
        wf_spec_name
    )

    return actions.PythonAction(action_def, action_ex=action_ex)


def build_action_by_name(action_name):
    action_def = actions.resolve_action_definition(action_name)

    action_cls = (actions.PythonAction if not action_def.spec
                  else actions.AdHocAction)

    return action_cls(action_def)
