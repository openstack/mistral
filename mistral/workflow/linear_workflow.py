# Copyright 2014 - Mirantis, Inc.
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

from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.workflow import base
from mistral.workflow import data_flow
from mistral.workflow import states

LOG = logging.getLogger(__name__)


class LinearWorkflowHandler(base.WorkflowHandler):
    """'Linear workflow' handler.

    This handler implements the workflow pattern which is based on
    direct transitions between tasks, i.e. after each task completion
    a decision should be made which tasks should run next based on
    result of task execution.
    For example, if there's a workflow consisting of three tasks 'A',
    'B' and 'C' where 'A' starts first then 'B' and 'C' can start second
    if certain associated with transition 'A'->'B' and 'A'->'C' evaluate
    to true.
    """
    def start_workflow(self, **params):
        self._set_execution_state(states.RUNNING)

        return [self._find_start_task()]

    def get_upstream_tasks(self, task_spec):
        # TODO(rakhmerov): For linear workflow it's pretty hard to do
        #  so we may need to get rid of it at all.
        return []

    def _find_start_task(self):
        return self.wf_spec.get_tasks()[self.wf_spec.get_start_task_name()]

    def _find_next_tasks(self, task_db):
        """Finds tasks that should run after completing given task.

        Expression 'on_finish' is not mutually exclusive to 'on_success'
         and 'on_error'.
        :param task_db: Task DB model.
        :return: List of task specifications.
        """
        task_specs = []

        t_name = task_db.name
        t_state = task_db.state

        tasks_spec = self.wf_spec.get_tasks()

        ctx = data_flow.evaluate_outbound_context(task_db)

        if t_state == states.ERROR:
            on_error = tasks_spec[t_name].get_on_error()

            if on_error:
                task_specs = self._get_tasks_to_schedule(on_error, ctx)

        elif t_state == states.SUCCESS:
            on_success = tasks_spec[t_name].get_on_success()

            if on_success:
                task_specs = self._get_tasks_to_schedule(on_success, ctx)

        if states.is_finished(t_state):
            on_finish = tasks_spec[t_name].get_on_finish()

            if on_finish:
                task_specs += self._get_tasks_to_schedule(on_finish, ctx)

        LOG.debug("Found tasks: %s" % task_specs)

        return task_specs

    def _get_tasks_to_schedule(self, task_conditions, ctx):
        task_specs = []

        for t_name, condition in task_conditions.iteritems():
            if expr.evaluate(condition, ctx):
                task_specs.append(self.wf_spec.get_tasks()[t_name])

        return task_specs
