# Copyright 2015 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2020 Nokia Software.
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
from mistral.services import actions as action_service


LOG = logging.getLogger(__name__)


@profiler.trace('action-handler-on-action-complete', hide_args=True)
def on_action_complete(action_ex, result):
    task_ex = action_ex.task_execution

    action = _build_action(action_ex)

    try:
        action.complete(result)
    except exc.MistralException as e:
        msg = (
            "Failed to complete action [error=%s, action=%s, task=%s]:\n%s"
            % (e, action_ex.name, task_ex.name, tb.format_exc())
        )

        LOG.error(msg)

        action.fail(msg)

        if task_ex:
            task_handler.force_fail_task(task_ex, msg)

        return

    if task_ex:
        task_handler.schedule_on_action_complete(action_ex)


@profiler.trace('action-handler-on-action-update', hide_args=True)
def on_action_update(action_ex, state):
    task_ex = action_ex.task_execution

    action = _build_action(action_ex)

    try:
        action.update(state)
    except exc.MistralException as e:
        # If the update of the action execution fails, do not fail
        # the action execution. Log the exception and re-raise the
        # exception.
        msg = (
            "Failed to update action [error=%s, action=%s, task=%s]:\n%s"
            % (e, action_ex.name, task_ex.name, tb.format_exc())
        )

        LOG.error(msg)

        raise

    if task_ex:
        task_handler.schedule_on_action_update(action_ex)


@profiler.trace('action-handler-build-action', hide_args=True)
def _build_action(action_ex):
    if isinstance(action_ex, models.WorkflowExecution):
        return actions.WorkflowAction(
            wf_name=action_ex.name,
            action_ex=action_ex
        )

    action_desc = action_service.get_system_action_provider().find(
        action_ex.name,
        action_ex.workflow_namespace
    )

    if action_desc is None:
        raise exc.InvalidActionException(
            "Failed to find action [action_name=%s]" %
            action_ex.name
        )

    return actions.RegularAction(action_desc, action_ex)


def build_action_by_name(action_name, namespace=''):
    action_desc = action_service.get_system_action_provider().find(
        action_name,
        namespace=namespace
    )

    if action_desc is None:
        raise exc.InvalidActionException(
            "Failed to find action [action_name=%s]" %
            action_name
        )

    return actions.RegularAction(action_desc)
