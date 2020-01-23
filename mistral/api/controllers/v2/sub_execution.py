# Copyright 2020 - Nokia Networks.
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
from pecan import request
from pecan import rest
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral.utils import rest_utils
from mistral.workflow import states

LOG = logging.getLogger(__name__)


def get_task_sub_executions_list(task_ex_id, filters, cur_depth):
    task_sub_execs = []

    with db_api.transaction():
        task_ex = db_api.get_task_execution(task_ex_id)

        if filters['errors_only'] and task_ex.state != states.ERROR:
            return []

        child_wf_executions = task_ex.workflow_executions

    for c_ex in child_wf_executions:
        task_sub_execs.extend(
            get_execution_sub_executions_list(
                c_ex.id,
                filters,
                cur_depth
            )
        )

    return task_sub_execs


def get_execution_sub_executions_list(wf_ex_id, filters, cur_depth):
    max_depth = filters['max_depth']
    include_output = filters['include_output']
    ex_sub_execs = []

    if 0 <= max_depth < cur_depth:
        return []

    with db_api.transaction():
        wf_ex = db_api.get_workflow_execution(wf_ex_id)

        wf_resource = _get_wf_resource_from_db_model(
            wf_ex,
            include_output)

        ex_sub_execs.append(wf_resource)

        task_execs = wf_ex.task_executions

    for t_ex in task_execs:
        task_sub_executions = get_task_sub_executions_list(
            t_ex.id,
            filters,
            cur_depth + 1
        )
        ex_sub_execs.extend(task_sub_executions)

    return ex_sub_execs


def _get_wf_resource_from_db_model(wf_ex, include_output):
    if include_output:
        rest_utils.load_deferred_fields(wf_ex, ['params', 'input', 'output'])
    else:
        rest_utils.load_deferred_fields(wf_ex, ['params', 'input'])

    return resources.Execution.from_db_model(wf_ex)


def _get_sub_executions(origin, id, filters):
    if origin == 'execution':
        return get_execution_sub_executions_list(id, filters, cur_depth=0)
    else:
        return get_task_sub_executions_list(id, filters, cur_depth=0)


class SubExecutionsController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Executions, types.uuid, bool, int, bool)
    def get(self, id, errors_only=False, max_depth=-1, include_output=False):
        """Return workflow execution report.

        :param id: The ID of the workflow execution or task execution
            to get the sub-executions of.
        :param errors_only: Optional. If True, only error paths of the
            execution tree are returned .
        :param max_depth: Optional. Limits the depth of recursion while
            obtaining the execution tree. If a value of the
            flag is a negative number then no limit is set.
        :param include_output: Optional. Include the output for all executions
            in the list.
        """
        origin = 'execution' if request.path.startswith('/v2/executions') \
            else 'task'

        LOG.info(
            "Fetching sub executions of %s [id=%s]",
            origin,
            id
        )

        filters = {
            'errors_only': errors_only,
            'max_depth': max_depth,
            'include_output': include_output
        }

        sub_executions_resource = _get_sub_executions(origin, id, filters)

        return resources.Executions.convert_with_links(
            sub_executions_resource,
            request.application_url,
        )
