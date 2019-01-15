# Copyright 2019 - Nokia Networks.
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
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.utils import rest_utils
from mistral.workflow import states


LOG = logging.getLogger(__name__)


def create_workflow_execution_entry(wf_ex):
    return resources.WorkflowExecutionReportEntry.from_db_model(wf_ex)


def create_task_execution_entry(task_ex):
    return resources.TaskExecutionReportEntry.from_db_model(task_ex)


def create_action_execution_entry(action_ex):
    return resources.ActionExecutionReportEntry.from_db_model(action_ex)


def update_statistics_with_task(stat, task_ex):
    if task_ex.state == states.RUNNING:
        stat.increment_running()
    elif task_ex.state == states.SUCCESS:
        stat.increment_success()
    elif task_ex.state == states.ERROR:
        stat.increment_error()
    elif task_ex.state == states.IDLE:
        stat.increment_idle()
    elif task_ex.state == states.PAUSED:
        stat.increment_paused()


def analyse_task_execution(task_ex_id, stat, filters, cur_depth):
    with db_api.transaction():
        task_ex = db_api.get_task_execution(task_ex_id)

        if filters['errors_only'] and task_ex.state != states.ERROR:
            return None

        update_statistics_with_task(stat, task_ex)

        entry = create_task_execution_entry(task_ex)

        child_executions = task_ex.executions

    entry.action_executions = []
    entry.workflow_executions = []

    for c_ex in child_executions:
        if isinstance(c_ex, db_models.ActionExecution):
            entry.action_executions.append(
                create_action_execution_entry(c_ex)
            )
        else:
            entry.workflow_executions.append(
                analyse_workflow_execution(c_ex.id, stat, filters, cur_depth)
            )

    return entry


def analyse_workflow_execution(wf_ex_id, stat, filters, cur_depth):
    with db_api.transaction():
        wf_ex = db_api.get_workflow_execution(wf_ex_id)

        entry = create_workflow_execution_entry(wf_ex)

        max_depth = filters['max_depth']

        # Don't get deeper into the workflow task executions if
        # maximum depth is defined and the current depth exceeds it.
        if 0 <= max_depth < cur_depth:
            return entry

        task_execs = wf_ex.task_executions

    entry.task_executions = []

    for t_ex in task_execs:
        task_exec_entry = analyse_task_execution(
            t_ex.id,
            stat,
            filters,
            cur_depth + 1
        )

        if task_exec_entry:
            entry.task_executions.append(task_exec_entry)

    return entry


def build_report(wf_ex_id, filters):
    report = resources.ExecutionReport()

    stat = resources.ExecutionReportStatistics()

    report.statistics = stat
    report.root_workflow_execution = analyse_workflow_execution(
        wf_ex_id,
        stat,
        filters,
        0
    )

    return report


class ExecutionReportController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.ExecutionReport, types.uuid, bool, int)
    def get(self, workflow_execution_id, errors_only=False, max_depth=-1):
        """Return workflow execution report.

        :param workflow_execution_id: The ID of the workflow execution to
            generate a report for.
        :param errors_only: Optional. If True, only error paths of the
            execution tree are included into the report. The root execution
            (with the specified id) is always included, but its tasks may
            or may not be included depending on this flag's value.
        :param max_depth: Optional. Limits the depth of recursion while
            obtaining the execution tree. That is, subworkflows of what
            maximum depth will be included into the report. If a value of the
            flag is a negative number then no limit is set.
            The root execution has depth 0 so if the flag is 0 then only
            the root execution, its tasks and their actions will be included.
            If some of the tasks in turn run workflows then these subworkflows
            will be also included but without their tasks. The algorithm will
            fully analyse their tasks only if max_depth is greater than zero.
        """

        LOG.info(
            "Fetch execution report [workflow_execution_id=%s]",
            workflow_execution_id
        )

        filters = {
            'errors_only': errors_only,
            'max_depth': max_depth
        }

        return build_report(workflow_execution_id, filters)
