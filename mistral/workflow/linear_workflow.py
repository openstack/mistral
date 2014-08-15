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

from mistral.workflow import base
from mistral.workflow import states


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

    def on_task_result(self, task_db, raw_result):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    def _find_start_task(self):
        return self.wf_spec.get_tasks()[self.wf_spec.get_start_task_name()]