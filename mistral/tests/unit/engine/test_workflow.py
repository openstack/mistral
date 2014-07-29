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

from mistral.engine import states
from mistral.engine import workflow
from mistral.tests import base
from mistral.workbook import parser as spec_parser


TASKS = [
    {
        'name': 'backup-vms',
        'state': states.IDLE,
        'task_spec': {
            'requires': {}
        }
    },
    {
        'name': 'create-vms',
        'state': states.SUCCESS,
        'task_spec': {
            'requires': {}
        }
    },
    {
        'name': 'attach-volume',
        'state': states.IDLE,
        'task_spec': {
            'requires': {
                'create-vms': ''
            }
        }
    }
]


class WorkflowTest(base.DbTestCase):
    def setUp(self):
        super(WorkflowTest, self).setUp()

    def test_find_workflow_tasks(self):
        wb_definition = base.get_resource("test_rest.yaml")

        tasks = workflow.find_workflow_tasks(
            spec_parser.get_workbook_spec_from_yaml(wb_definition),
            "attach-volumes"
        )

        self.assertEqual(2, len(tasks))

        self._assert_single_item(tasks, name='create-vms')
        self._assert_single_item(tasks, name='attach-volumes')

    def test_find_workflow_tasks_order(self):
        wb_definition = base.get_resource("test_order.yaml")

        tasks = workflow.find_workflow_tasks(
            spec_parser.get_workbook_spec_from_yaml(wb_definition),
            'task'
        )

        self.assertEqual(5, len(tasks))

        completed = set()

        for i, task in enumerate(tasks):
            self.assertTrue(set(task.requires.keys()).issubset(completed),
                            "Task %s isn't completed yet" % task.name)
            completed.add(task.name)

    def test_tasks_to_start(self):
        tasks_to_start = workflow.find_resolved_tasks(TASKS)
        self.assertEqual(len(tasks_to_start), 2)
