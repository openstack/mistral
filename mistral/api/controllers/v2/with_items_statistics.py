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

from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral.utils import rest_utils
from oslo_log import log as logging
from pecan import abort
from pecan import rest
from wsmeext.pecan import wsexpose

LOG = logging.getLogger(__name__)


def build_statistics(task_id):
    stat = resources.WithItemsStatisticsResource()
    total_items, items_group_by_state = fetch_statistics(task_id)
    stat.set_statistics(total_items, items_group_by_state)
    return stat


def fetch_statistics(task_id):
    with db_api.transaction():
        task_ex = db_api.get_task_execution(task_id)
        type = task_ex.type
        total_items, items_group_by_state = (
            db_api.get_with_items_statistics_of_task(task_id, type)
        )
    return total_items, items_group_by_state


def get_task_execution(task_id):
    try:
        return db_api.get_task_execution(task_id)
    except Exception as e:
        LOG.error(f"Failed to fetch task execution: {e}")
        abort(404, f"Task execution {task_id} not found.")


def is_with_items(task_id):
    with db_api.transaction():
        task_ex = db_api.get_task_execution(task_id)
        return bool(task_ex.runtime_context.get('with_items', {}))


class WithItemsStatisticsController(rest.RestController):

    @rest_utils.wrap_wsme_controller_exception
    @wsexpose(resources.WithItemsStatisticsResource, types.uuid)
    def get(self, task_id):
        """Return statistics for the specified with-items Task Execution

        :param task_id: UUID of the task execution to
            retrieve statistics for.
        """

        LOG.debug("Fetch task with-items statistics [id=%s]", task_id)
        get_task_execution(task_id)

        if not is_with_items(task_id):
            abort(404, f"Task {task_id} is not with-items type")

        return build_statistics(task_id)
