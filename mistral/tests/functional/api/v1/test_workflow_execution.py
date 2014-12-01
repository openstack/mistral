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

    _version = 1

    def test_reverse_flow(self):
        text = base.get_resource(
            'data_flow/task_with_diamond_dependencies.yaml')
        self.client.prepare_workbook('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'send_greeting')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_full_name']['string'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_address')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_address']['string'],
                         "To John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_greeting']['string'],
                         "Dear John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'send_greeting')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['send_greeting']['string'],
                         "To John Doe. Dear John Doe,..")

    def test_task_with_two_dependencies(self):
        text = base.get_resource(
            'data_flow/task_with_two_dependencies.yaml')
        self.client.prepare_workbook('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'send_greeting')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_greeting']['greeting'],
                         "Cheers!")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'send_greeting')
        task_output = json.loads(task['output'])
        self.assertTrue(task_output['task']['send_greeting']['greeting_sent'])

    def test_direct_flow_tasks_on_success(self):
        text = base.get_resource(
            'data_flow/three_subsequent_tasks.yaml')
        self.client.prepare_workbook('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'build_full_name')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_greeting']['greeting'],
                         "Hello, John Doe!")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'send_greeting')
        task_output = json.loads(task['output'])
        self.assertTrue(task_output['task']['send_greeting']['greeting_sent'])

    def test_two_dependent_tasks(self):
        text = base.get_resource(
            'data_flow/two_dependent_tasks.yaml')
        self.client.prepare_workbook('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'build_greeting')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_greeting']['greeting'],
                         "Hello, John Doe!")

    def test_two_subsequent_tasks(self):
        text = base.get_resource(
            'data_flow/two_subsequent_tasks.yaml')
        self.client.prepare_workbook('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', CONTEXT, 'build_full_name')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_full_name')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['build_full_name']['full_name'],
                         "John Doe")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'build_greeting')
        task_output = json.loads(task['output'])
        self.assertEqual(
            task_output['task']['build_greeting']['greeting']['greet_message'],
            "Hello, John Doe!")

    def test_mixed_workflow(self):
        text = base.get_resource(
            'test_mixed_flow.yaml')
        self.client.prepare_workbook('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', {}, 'task2')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'task1')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['task1']['string'],
                         "workflow is")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'task2')
        task_output = json.loads(task['output'])
        self.assertEqual(
            task_output['task']['task2']['string'],
            "workflow is complete")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'task3')
        task_output = json.loads(task['output'])
        self.assertEqual(
            task_output['task']['task3']['string'],
            "workflow is complete !")

    def test_direct_workflow_all_keywords(self):
        text = base.get_resource(
            'test_direct_flow_all_keywords.yaml')
        self.client.prepare_workbook('test', text)

        _, ex = self.client.create_execution_wait_success(
            'test', {}, 'task1')

        task = self.client.get_task_by_name('test', ex['id'],
                                            'task2')
        task_output = json.loads(task['output'])
        self.assertEqual(task_output['task']['task2']['string'],
                         "workflow is")

        task = self.client.get_task_by_name('test', ex['id'],
                                            'task4')
        task_output = json.loads(task['output'])
        self.assertEqual(
            task_output['task']['task4']['string'],
            "workflow is complete!")
