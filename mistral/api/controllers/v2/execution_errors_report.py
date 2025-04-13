# Copyright 2022 - NetCracker Technology Corp.
# Modified in 2025 by NetCracker Technology Corp.
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
from pecan import rest
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral.utils import rest_utils
from mistral.workflow import states


LOG = logging.getLogger(__name__)


def create_workflow_error_report_entry(wf_ex):
    state_info = wf_ex.state_info
    state_info = (state_info.splitlines()[0]).strip()
    return resources.ExecutionErrorReportEntry(
        id=wf_ex.id,
        parent_id=wf_ex.task_execution_id,
        type="WORKFLOW",
        name=wf_ex.name,
        error=state_info
    )


def create_task_error_report_entry(task_ex):
    state_info = task_ex.state_info
    state_info = state_info.splitlines()[0]
    state_info = (state_info.split("[")[0]).strip()
    return resources.ExecutionErrorReportEntry(
        id=task_ex.id,
        parent_id=task_ex.workflow_execution_id,
        type="TASK",
        name=task_ex.name,
        error=state_info
    )


def create_action_error_report_entry(action_ex, idx):
    result = action_ex.output["result"]
    result = result.split(', ')
    error = result[2].split('msg=')[1][1:-2]
    attributes = ""
    params = ""
    # attributes = result[3].split('attributes=')[1][1:-1]
    # params = result[4].split('params=')[1][1:-2]
    return resources.ExecutionErrorReportEntry(
        id=action_ex.id,
        parent_id=action_ex.task_execution_id,
        type="ACTION",
        name=action_ex.name,
        error=error,
        idx=idx,
        attributes=attributes,
        params=params
    )


def search_for_errors_recursively(wf_ex):
    errors = []
    if wf_ex.state == states.ERROR:
        errors.append(create_workflow_error_report_entry(wf_ex))

    failed_task_exs = db_api.get_task_executions(
        workflow_execution_id=wf_ex.id,
        state=states.ERROR,
        error_handled=False
    )

    for task_ex in failed_task_exs:
        if task_ex.state == states.ERROR:
            errors.append(create_task_error_report_entry(task_ex))

        for i, action_ex in enumerate(task_ex.action_executions):
            if action_ex.state == states.ERROR:
                errors.append(create_action_error_report_entry(action_ex, i))

        for sub_wf_ex in task_ex.workflow_executions:
            errors.extend(search_for_errors_recursively(sub_wf_ex))

    return errors


def build_report(wf_ex_id):
    errors = []
    with db_api.transaction():
        wf_ex = db_api.get_workflow_execution(wf_ex_id)
        errors = search_for_errors_recursively(wf_ex)

    report = resources.ExecutionErrorsReport(errors=errors)
    return report


class ExecutionErrorsReportController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.ExecutionErrorsReport, types.uuid)
    def get(self, workflow_execution_id):
        """Return workflow execution report.

        :param workflow_execution_id: The ID of the workflow execution to
            generate a report for.
        """

        LOG.info(
            "Fetch execution errors report [workflow_execution_id=%s]",
            workflow_execution_id
        )

        return build_report(workflow_execution_id)
