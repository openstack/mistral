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

# TODO(rakhmerov): Deprecated in favor of package 'mistral.engine1'.

import networkx as nx
from networkx.algorithms import traversal

from mistral.engine import states
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def find_workflow_tasks(workbook, task_name):
    wb_tasks = workbook.tasks
    full_graph = nx.DiGraph()

    for t in wb_tasks:
        full_graph.add_node(t)

    _update_dependencies(wb_tasks, full_graph)

    # Find the list of the tasks in the order they're supposed to be executed.
    task_spec = wb_tasks[task_name]

    return [node for node
            in traversal.dfs_postorder_nodes(full_graph.reverse(), task_spec)]


def find_resolved_tasks(tasks):
    # We need to analyse graph and see which tasks are ready to start
    resolved_tasks = []
    delayed_tasks = []
    allows = []
    for t in tasks:
        if t['state'] == states.SUCCESS:
            allows += [t['name']]
    allow_set = set(allows)
    for t in tasks:
        deps = t['task_spec'].get('requires', {}).keys()
        if len(set(deps) - allow_set) == 0:
            # all required tasks, if any, are SUCCESS
            if t['state'] == states.IDLE:
                resolved_tasks.append(t)
            elif t['state'] == states.DELAYED:
                delayed_tasks.append(t)
    return resolved_tasks, delayed_tasks


def _get_checked_tasks(target_tasks):
    checked_tasks = []
    for t in target_tasks:
        # TODO(nmakhotkin): see and evaluate YAQL with data from context
        checked_tasks.append(t)
    return checked_tasks


def _get_tasks_to_schedule(target_tasks, workbook):
    tasks_to_schedule = _get_checked_tasks(target_tasks)
    return [workbook.tasks.get(t_name) for t_name in tasks_to_schedule]


def find_tasks_after_completion(task, workbook):
    """Determine tasks which should be scheduled after completing
    given task. Expression 'on_finish' is not mutually exclusive to
    'on_success' and 'on_error'.

    :param task: Task object
    :param workbook: Workbook Entity
    :return: list of task dictionaries.
    """
    state = task['state']
    found_tasks = []
    LOG.debug("Recieved task %s: %s" % (task['name'], state))

    if state == states.ERROR:
        tasks_on_error = workbook.tasks.get(task['name']).get_on_error()
        if tasks_on_error:
            found_tasks = _get_tasks_to_schedule(tasks_on_error, workbook)

    elif state == states.SUCCESS:
        tasks_on_success = workbook.tasks.get(task['name']).get_on_success()
        if tasks_on_success:
            found_tasks = _get_tasks_to_schedule(tasks_on_success, workbook)

    if states.is_finished(state):
        tasks_on_finish = workbook.tasks.get(task['name']).get_on_finish()
        if tasks_on_finish:
            found_tasks += _get_tasks_to_schedule(tasks_on_finish, workbook)

    LOG.debug("Found tasks: %s" % found_tasks)

    workflow_tasks = []
    for t in found_tasks:
        workflow_tasks += find_workflow_tasks(workbook, t.name)

    LOG.debug("Workflow tasks to schedule: %s" % workflow_tasks)

    return workflow_tasks


def is_finished(tasks):
    return all(states.is_finished(task['state']) for task in tasks)


def is_success(tasks):
    return all(task['state'] == states.SUCCESS for task in tasks)


def is_error(tasks):
    return any(task['state'] == states.ERROR and
               not task['task_spec'].get('on-error', {}) and
               not task['task_spec'].get('on-finish', {}) for task in tasks)


def _get_dependency_tasks(tasks_spec, task_spec):
    dep_task_names = tasks_spec[task_spec.name].get_requires()

    if len(dep_task_names) == 0:
        return []

    dep_t_specs = set()

    for t_spec in tasks_spec:
        for t_name in dep_task_names:
            if t_name == t_spec.name:
                dep_t_specs.add(t_spec)

    return dep_t_specs


def _update_dependencies(tasks_spec, graph):
    for t_spec in tasks_spec:
        for dep_t_spec in _get_dependency_tasks(tasks_spec, t_spec):
            graph.add_edge(dep_t_spec, t_spec)
