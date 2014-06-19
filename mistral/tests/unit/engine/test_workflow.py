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

from mistral import dsl_parser as parser
from mistral.engine import states
from mistral.engine import workflow
from mistral.tests import base

TASKS = [
    {
        'requires': {},
        'name': 'backup-vms',
        'state': states.IDLE
    },
    {
        'requires': {},
        'name': 'create-vms',
        'state': states.SUCCESS
    },
    {
        'requires': ['create-vms'],
        'name': 'attach-volume',
        'state': states.IDLE
    }
]


class WorkflowTest(base.DbTestCase):
    def setUp(self):
        super(WorkflowTest, self).setUp()
        self.parser = parser.get_workbook(base.get_resource("test_rest.yaml"))

    def test_find_workflow_tasks(self):
        tasks = workflow.find_workflow_tasks(self.parser, "attach-volumes")

        self.assertEqual(2, len(tasks))

        self._assert_single_item(tasks, name='create-vms')
        self._assert_single_item(tasks, name='attach-volumes')

    def test_tasks_to_start(self):
        tasks_to_start = workflow.find_resolved_tasks(TASKS)
        self.assertEqual(len(tasks_to_start), 2)
