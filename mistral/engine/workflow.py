# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

from mistral.engine import states


def find_workflow_tasks(wb_dsl, target_task_name):
    dsl_tasks = wb_dsl.get_tasks()
    full_graph = nx.DiGraph()
    for t in dsl_tasks:
        full_graph.add_node(t)

    _update_dependencies(dsl_tasks, full_graph)

    graph = _get_subgraph(full_graph, target_task_name)
    tasks = []
    for node in graph:
        task = {'name': node}
        task.update(dsl_tasks[node])
        tasks.append(task)

    return tasks


def find_tasks_to_start(tasks):
    # We need to analyse graph and see which tasks are ready to start
    return _get_resolved_tasks(tasks)


def is_finished(tasks):
    return all(states.is_finished(task['state']) for task in tasks)


def is_success(tasks):
    return all(task['state'] == states.SUCCESS for task in tasks)


def is_error(tasks):
    return all(task['state'] == states.ERROR for task in tasks)


def _get_subgraph(full_graph, task_name):
    nodes_set = traversal.dfs_predecessors(full_graph.reverse(),
                                           task_name).keys()
    nodes_set.append(task_name)

    return full_graph.subgraph(nodes_set)


def _get_dependency_tasks(tasks, task):
    if 'dependsOn' not in tasks[task]:
        return []

    deps = set()
    for t in tasks:
        for dep in tasks[task]['dependsOn']:
            if dep == t:
                deps.add(t)

    return deps


def _update_dependencies(tasks, graph):
    for task in tasks:
        for dep in _get_dependency_tasks(tasks, task):
            graph.add_edge(dep, task)


def _get_resolved_tasks(tasks):
    resolved_tasks = []
    allows = []
    for t in tasks:
        if t['state'] == states.SUCCESS:
            allows += [t['name']]
    allow_set = set(allows)
    for t in tasks:
        if len(set(t.get('dependencies', [])) - allow_set) == 0:
            if t['state'] == states.IDLE:
                resolved_tasks.append(t)
    return resolved_tasks
