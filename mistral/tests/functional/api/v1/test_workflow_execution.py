# Copyright 2013 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json

from mistral.tests.functional import base


CONTEXT = {
    'person': {
        'first_name': 'John',
        'last_name': 'Doe',
    }
}


class MistralWorkflowExecutionTests(base.TestCaseAdvanced):
    def test_reverse_flow(self):
        text = base.get_resource(
            'resources/data_flow/task_with_diamond_dependencies.yaml')
        self.client.upload_workbook_definition('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'send_greeting')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_full_name']['string'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_address')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_address']['string'],
                         "To John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_greeting']['string'],
                         "Dear John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'send_greeting')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['send_greeting']['string'],
                         "To John Doe. Dear John Doe,..")

    def test_task_with_two_dependencies(self):
        text = base.get_resource(
            'resources/data_flow/task_with_two_dependencies.yaml')
        self.client.upload_workbook_definition('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'send_greeting')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_greeting']['greeting'],
                         "Cheers!")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'send_greeting')
        task = json.loads(task['output'])
        self.assertTrue(task['task']['send_greeting']['greeting_sent'])

    def test_direct_flow_tasks_on_success(self):
        text = base.get_resource(
            'resources/data_flow/three_subsequent_tasks.yaml')
        self.client.upload_workbook_definition('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'build_full_name')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_greeting']['greeting'],
                         "Hello, John Doe!")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'send_greeting')
        task = json.loads(task['output'])
        self.assertTrue(task['task']['send_greeting']['greeting_sent'])

    def test_two_dependent_tasks(self):
        text = base.get_resource(
            'resources/data_flow/two_dependent_tasks.yaml')
        self.client.upload_workbook_definition('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'build_greeting')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_greeting']['greeting'],
                         "Hello, John Doe!")

    def test_two_subsequent_tasks(self):
        text = base.get_resource(
            'resources/data_flow/two_subsequent_tasks.yaml')
        self.client.upload_workbook_definition('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'build_full_name')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task = json.loads(task['output'])
        self.assertEqual(task['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task = json.loads(task['output'])
        self.assertEqual(
            task['task']['build_greeting']['greeting']['greet_message'],
            "Hello, John Doe!")
