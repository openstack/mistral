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
        task_name = kwargs.get('task_name')

        task_spec = self.wf_spec.get_tasks().get(task_name)

        if not task_spec:
            msg = 'Invalid task name [wf_spec=%s, task_name=%s]' % \
                  (self.wf_spec, task_name)
            raise exc.WorkflowException(msg)

        task_specs = self._find_tasks_with_no_dependencies(task_spec)

        if len(task_specs) > 0:
            state = self.exec_db.state

            if states.is_valid_transition(self.exec_db.state, states.RUNNING):
                self.exec_db.state = states.RUNNING
            else:
                msg = "Can't change workflow state [execution=%s," \
                      " state=%s -> %s]" % \
                      (self.exec_db, state, states.RUNNING)
                raise exc.WorkflowException(msg)

        return task_specs

    def on_task_result(self, task_db, task_result):
        task_db.state = \
            states.ERROR if task_result.is_error() else states.SUCCESS
        task_db.output = task_result.data

        if task_db.state == states.ERROR:
            # No need to check state transition since it's possible to switch
            # to ERROR state from any other state.
            self.exec_db.state = states.ERROR
            return []

        return self._find_resolved_tasks()

    def _find_tasks_with_no_dependencies(self, task_spec):
        """Given a target task name finds tasks with no dependencies.

        :param task_spec: Target task specification in the workflow graph
            that dependencies are unwound from.
        :return: Tasks with no dependencies.
        """
        tasks_spec = self.wf_spec.get_tasks()

        graph = self._build_graph(tasks_spec)

        # Unwind tasks from the target task
        # and filter out tasks with dependencies.
        return [
            t_spec for t_spec in
            traversal.dfs_postorder_nodes(graph.reverse(), task_spec)
            if not t_spec.get_requires()
        ]

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
        dep_task_names = tasks_spec[task_spec.get_name()].get_requires()

        if len(dep_task_names) == 0:
            return []

        dep_t_specs = set()

        for t_spec in tasks_spec:
            for t_name in dep_task_names:
                if t_name == t_spec.get_name():
                    dep_t_specs.add(t_spec)

        return dep_t_specs

    def _find_resolved_tasks(self):
        """Finds all tasks with resolved dependencies.

        :return: Tasks with resolved dependencies.
        """
        # TODO(rakhmerov): Implement.
        raise NotImplementedError
