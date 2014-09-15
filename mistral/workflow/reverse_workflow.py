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

from mistral.engine1 import commands
from mistral import exceptions as exc
from mistral.workflow import base
from mistral.workflow import states


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

    def start_workflow(self, **params):
        task_name = params.get('task_name')

        task_spec = self.wf_spec.get_tasks().get(task_name)

        if not task_spec:
            msg = 'Invalid task name [wf_spec=%s, task_name=%s]' % \
                  (self.wf_spec, task_name)
            raise exc.WorkflowException(msg)

        task_specs = self._find_tasks_without_dependencies(task_spec)

        if len(task_specs) > 0:
            self._set_execution_state(states.RUNNING)

        return [commands.RunTask(t_s) for t_s in task_specs]

    def get_upstream_tasks(self, task_spec):
        return [self.wf_spec.get_tasks()[t_name]
                for t_name in task_spec.get_requires() or []]

    def _find_next_commands(self, task_db):
        """Finds all tasks with resolved dependencies and return them
         in the form of engine commands.

        :param task_db: Task DB model causing the operation.
        :return: Tasks with resolved dependencies.
        """

        # If cause task is the target task of the workflow then
        # there's no more tasks to start.
        if self.exec_db.start_params['task_name'] == task_db.name:
            return []

        # We need to analyse the graph and see which tasks are ready to start.
        resolved_task_specs = []
        success_task_names = set()

        for t in self.exec_db.tasks:
            if t.state == states.SUCCESS:
                success_task_names.add(t.name)

        for t_spec in self.wf_spec.get_tasks():
            # Skip task if it doesn't have a direct dependency
            # on the cause task.
            if task_db.name not in t_spec.get_requires():
                continue

            if not (set(t_spec.get_requires()) - success_task_names):
                t_db = self._find_db_task(t_spec.get_name())

                if not t_db or t_db.state == states.IDLE:
                    resolved_task_specs.append(t_spec)

        return [commands.RunTask(t_s) for t_s in resolved_task_specs]

    def _find_tasks_without_dependencies(self, task_spec):
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

    def _find_db_task(self, name):
        db_tasks = filter(lambda t: t.name == name, self.exec_db.tasks)

        return db_tasks[0] if db_tasks else None
