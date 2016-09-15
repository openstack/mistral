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

import networkx as nx
from networkx.algorithms import traversal

from mistral import exceptions as exc
from mistral.workflow import base
from mistral.workflow import commands
from mistral.workflow import data_flow
from mistral.workflow import lookup_utils
from mistral.workflow import states


class ReverseWorkflowController(base.WorkflowController):
    """'Reverse workflow controller.

    This controller implements the workflow pattern which is based on
    dependencies between tasks, i.e. each task in a workflow graph
    may be dependent on other tasks. To run this type of workflow
    user must specify a task name that serves a target node in the
    graph that the algorithm should come to by resolving all
    dependencies.
    For example, if there's a workflow consisting of two tasks
    'A' and 'B' where 'A' depends on 'B' and if we specify a target
    task name 'A' then the controller first will run task 'B' and then,
    when a dependency of 'A' is resolved, will run task 'A'.
    """

    __workflow_type__ = "reverse"

    def _find_next_commands(self, task_ex):
        """Finds all tasks with resolved dependencies.

         This method finds all tasks with resolved dependencies and
         returns them in the form of workflow commands.
        """
        cmds = super(ReverseWorkflowController, self)._find_next_commands(
            task_ex
        )

        # TODO(rakhmerov): Adapt reverse workflow to non-locking model.
        # 1. Task search must use task_ex parameter.
        # 2. When a task has more than one dependency it's possible to
        #   get into 'phantom read' phenomena and create multiple instances
        #   of the same task. So 'unique_key' in conjunction with 'wait_flag'
        #   must be used to prevent this.

        task_specs = self._find_task_specs_with_satisfied_dependencies()

        return cmds + [
            commands.RunTask(
                self.wf_ex,
                self.wf_spec,
                t_s,
                self.get_task_inbound_context(t_s)
            )
            for t_s in task_specs
        ]

    def _get_target_task_specification(self):
        task_name = self.wf_ex.params.get('task_name')

        task_spec = self.wf_spec.get_tasks().get(task_name)

        if not task_spec:
            raise exc.WorkflowException(
                'Invalid task name [wf_spec=%s, task_name=%s]' %
                (self.wf_spec, task_name)
            )

        return task_spec

    def _get_upstream_task_executions(self, task_spec):
        t_specs = [
            self.wf_spec.get_tasks()[t_name]
            for t_name in self.wf_spec.get_task_requires(task_spec)
            or []
        ]

        return list(
            filter(
                lambda t_e: t_e.state == states.SUCCESS,
                lookup_utils.find_task_executions_by_specs(
                    self.wf_ex.id,
                    t_specs
                )
            )
        )

    def evaluate_workflow_final_context(self):
        task_execs = lookup_utils.find_task_executions_by_spec(
            self.wf_ex.id,
            self._get_target_task_specification()
        )

        # NOTE: For reverse workflow there can't be multiple
        # executions for one task.
        assert len(task_execs) <= 1

        return data_flow.evaluate_task_outbound_context(task_execs[0])

    def get_logical_task_state(self, task_ex):
        # TODO(rakhmerov): Implement.
        return task_ex.state, task_ex.state_info, 0

    def is_error_handled_for(self, task_ex):
        return task_ex.state != states.ERROR

    def all_errors_handled(self):
        task_execs = lookup_utils.find_error_task_executions(self.wf_ex.id)

        return len(task_execs) == 0

    def _find_task_specs_with_satisfied_dependencies(self):
        """Given a target task name finds tasks with no dependencies.

        :return: Task specifications with no dependencies.
        """
        tasks_spec = self.wf_spec.get_tasks()

        graph = self._build_graph(tasks_spec)

        # Unwind tasks from the target task
        # and filter out tasks with dependencies.
        return [
            t_s for t_s in
            traversal.dfs_postorder_nodes(
                graph.reverse(),
                self._get_target_task_specification()
            )
            if self._is_satisfied_task(t_s)
        ]

    def _is_satisfied_task(self, task_spec):
        if lookup_utils.find_task_executions_by_spec(
                self.wf_ex.id, task_spec):
            return False

        if not self.wf_spec.get_task_requires(task_spec):
            return True

        success_t_names = set()

        for t_ex in self.wf_ex.task_executions:
            if t_ex.state == states.SUCCESS:
                success_t_names.add(t_ex.name)

        return not (
            set(self.wf_spec.get_task_requires(task_spec)) - success_t_names
        )

    def _build_graph(self, tasks_spec):
        graph = nx.DiGraph()

        # Add graph nodes.
        for t in tasks_spec:
            graph.add_node(t)

        # Add graph edges.
        for t_spec in tasks_spec:
            for dep_t_spec in self._get_dependency_tasks(tasks_spec, t_spec):
                graph.add_edge(dep_t_spec, t_spec)

        return graph

    def _get_dependency_tasks(self, tasks_spec, task_spec):
        dep_task_names = self.wf_spec.get_task_requires(task_spec)

        if len(dep_task_names) == 0:
            return []

        dep_t_specs = set()

        for t_spec in tasks_spec:
            for t_name in dep_task_names:
                if t_name == t_spec.get_name():
                    dep_t_specs.add(t_spec)

        return dep_t_specs
