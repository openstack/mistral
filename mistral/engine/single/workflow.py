# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import networkx as nx
from networkx.algorithms import traversal

from mistral.db import api as db_api
from mistral.engine import states
from mistral.engine.single import task
from mistral.openstack.common import log


LOG = log.getLogger(__name__)


def create_task(task_name, task_data, dsl):
    return task.MistralTask(
        allows=task_name,
        depends_on=task_data.get("dependsOn", None),
        name=task_name,
        dsl=dsl
    )


class MistralWorkflow(object):
    def __init__(self, target_task_name):
        self.target_task = target_task_name
        self.execution = None
        self.tasks = []
        self._graph = nx.DiGraph()
        self.results = {}

    def _get_dependency_tasks(self, task):
        if not task.depends_on:
            return []
        deps = set()
        for t in self.tasks:
            for dep in task.depends_on:
                if dep in t.allows:
                    deps.add(t)
        return deps

    def _update_dependencies(self):
        for task in self.tasks:
            for dep in self._get_dependency_tasks(task):
                self._graph.add_edge(dep, task)

    def add(self, item):
        if not isinstance(item, task.MistralTask):
            raise RuntimeError("Argument is not a MistralTask:" + item)
        self.tasks.append(item)
        self._graph.add_node(item)
        self._update_dependencies()

    def freeze(self):
        self._graph = nx.freeze(_get_subgraph(self._graph, self.target_task))
        self.tasks = [item for item in self._graph]

    #NOTE: this method should be called only within DB transaction.
    def create_tasks(self):
        for t in self.tasks:
            values = {
                'name': t.name,
                'state': t.state,
                'service_dsl': t.service_dsl,
                'action_dsl': t.action_dsl,
                'dependencies': t.depends_on
            }
            task = db_api.task_create(self.execution['workbook_name'],
                                      self.execution['id'], values)
            t.id = task['id']

    def get_resolved_tasks(self):
        tasks = db_api.tasks_get(self.execution['workbook_name'],
                                 self.execution['id'])
        resolved_tasks = []
        allows = []
        for t in tasks:
            if t['state'] == states.SUCCESS:
                allows += [t['name']]
            task = self._get_task(t['name'])
            task.id = t['id']
            task.state = t['state']

        allow_set = set(allows)
        for t in self.tasks:
            if len(set(t.depends_on) - allow_set) == 0:
                resolved_tasks.append(t)
        return resolved_tasks

    def run_resolved_tasks(self):
        LOG.debug("Workflow is running, target task - %s"
                  % self.target_task)
        resolved_tasks = self.get_resolved_tasks()
        for t in resolved_tasks:
            if t.state == states.IDLE:
                self.results.update({t.name: self._run_task(t)})

    #NOTE: this method should be called only within DB transaction.
    def update_task_state(self, task_id, state):
        t = db_api.task_update(self.execution['workbook_name'],
                               self.execution['id'],
                               task_id, {'state': state})
        task = self._get_task(t['name'])
        task.state = state
        return t

    def _get_task(self, task_name):
        for t in self.tasks:
            if t.name == task_name:
                return t

    def _run_task(self, task):
        t = self.update_task_state(task.id, states.RUNNING)

        #TODO(nmakhotkin) make it more configurable
        kwargs = {}
        if t['service_dsl']['type'] == 'REST_API':
            kwargs.update({
                'headers': {
                    'Mistral-Workbook-Name': t['workbook_name'],
                    'Mistral-Execution-Id': t['execution_id'],
                    'Mistral-Task-Id': t['id'],
                }
            })
        return task.run(**kwargs)


def _get_node_by_name(graph, name):
    for node in graph:
        if node.name == name:
            return node
    return None


def _get_subgraph(full_graph, task_name):
    node = _get_node_by_name(full_graph, task_name)
    nodes_set = traversal.dfs_predecessors(full_graph.reverse(),
                                           node).keys()
    nodes_set.append(node)
    return full_graph.subgraph(nodes_set)
