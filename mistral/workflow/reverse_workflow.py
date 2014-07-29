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

from mistral.engine1 import states
from mistral import exceptions as exc
from mistral.workflow import base


class ReverseWorkflowHandler(base.WorkflowHandler):
    """'Reverse workflow' handler.

    This handler implements the workflow pattern which is based on
    dependencies between tasks, i.e. each task in a workflow graph
    may be dependent on other tasks. To run this type of workflow
    user must specify a task name that serves a target node in the
    graph that the algorithm should come to by resolving all
    dependencies.
    For example, if there's a workflow consisting of two tasks
    'A' and 'B' where 'A' depends on 'B' and if we specify a target
    task name 'A' then the handler first will run task 'B' and then,
    when a dependency of 'A' is resolved, will run task 'A'.
    """

    def start_workflow(self, **kwargs):
        wf_spec = self.exec_db.wf_spec

        task_name = kwargs.get('task_name')

        if task_name not in wf_spec.tasks:
            msg = 'Invalid task name [wf_spec=%s, task_name=%s]' % \
                  (wf_spec, task_name)
            raise exc.WorkflowException(msg)

        return self._find_tasks_with_no_dependencies(task_name)

    def on_task_result(self, task, task_result):
        task.state = states.ERROR if task_result.is_error() else states.SUCCESS
        task.output = task_result.data

        if task.state == states.ERROR:
            # No need to check state transition since it's possible to switch
            # to ERROR state from any other state.
            self.exec_db.state = states.ERROR
            return []

        return self._find_resolved_tasks()

    def _find_tasks_with_no_dependencies(self, target_task_name):
        """Given a target task name finds tasks with no dependencies.

        :param target_task_name: Name of the target task in the workflow graph
            that dependencies are unwound from.
        :return: Tasks with no dependencies.
        """
        # TODO(rakhmerov): Implement.
        raise NotImplemented

    def _find_resolved_tasks(self):
        """Finds all tasks with resolved dependencies.

        :return: Tasks with resolved dependencies.
        """
        # TODO(rakhmerov): Implement.
        raise NotImplemented
