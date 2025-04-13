# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_log import log as logging
from pecan import abort
from pecan import rest
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral.utils import rest_utils

LOG = logging.getLogger(__name__)


def fetch_statistics(wf_ex_id, current_only):
    with db_api.transaction():
        total_tasks, tasks_group_by_state = (
            db_api.get_tasks_statistics_of_execution(wf_ex_id, current_only)
        )
    return total_tasks, tasks_group_by_state


def build_statistics(wf_ex_id, current_only):

    stat = resources.TasksStatisticsResource()
    total_tasks, tasks_group_by_state = fetch_statistics(
        wf_ex_id,
        current_only
    )
    stat.set_statistics(total_tasks, tasks_group_by_state)
    return stat


def _get_workflow_execution(workflow_execution_id):
    try:
        return db_api.get_workflow_execution(workflow_execution_id)
    except Exception as e:
        LOG.error(f"Failed to fetch workflow execution: {e}")
        abort(404, f"Workflow execution {workflow_execution_id} not found.")


def is_it_true(value):
    return value.lower() in ('true', 'yes', '1')


class TasksStatisticsController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.TasksStatisticsResource, types.uuid,
                         is_it_true)
    def get(self, workflow_execution_id, current_only="False"):
        """Return tasks execution statistics.

        :param workflow_execution_id: The ID of the workflow execution to
            generate a tasks statistics for.
        :param current_only: Optional. If True, only tasks of root workflow
            execution will be counted.
        """

        LOG.info(
            "Fetch tasks execution statistics [workflow_execution_id=%s]",
            workflow_execution_id
        )

        wf_ex = _get_workflow_execution(workflow_execution_id)

        if not current_only and wf_ex.root_execution_id is not None:
            abort(400, ("Request error: For current_only=False, "
                        "workflow_execution_id must refer to a root "
                        "workflow execution. The provided ID refers to a "
                        "non-root execution."))

        return build_statistics(workflow_execution_id, current_only)
