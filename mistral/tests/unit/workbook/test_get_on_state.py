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

SAMPLE_TASK_SPEC = {
    'action': 'MyRest:create-vm',
    'name': 'create-vms',
    'on-success': ["format-volumes", {'task1': 'expression'}, {'task2': ''}],
    'on-finish': "attach-volumes",
    'on-error': ["task1", "task2"]
}

import unittest2

from mistral.workbook import tasks


class GetOnStateTest(unittest2.TestCase):
    def setUp(self):
        self.task = tasks.TaskSpec(SAMPLE_TASK_SPEC)

    def test_state_finish(self):
        on_finish = self.task.get_on_finish()
        self.assertIsInstance(on_finish, dict)
        self.assertIn("attach-volumes", on_finish)

    def test_state_error(self):
        on_error = self.task.get_on_error()
        self.assertIsInstance(on_error, dict)
        self.assertEqual(len(on_error), 2)
        self.assertIn("task1", on_error)

    def test_state_success(self):
        on_success = self.task.get_on_success()
        self.assertIsInstance(on_success, dict)
        self.assertEqual(len(on_success), 3)
        self.assertIn("task1", on_success)
        self.assertIsNotNone(on_success["task1"])
