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

import eventlet

eventlet.monkey_patch()

import uuid
import time
import mock

from mistral.tests import base
from mistral.cmd import launch
from mistral.engine import states
from mistral.db import api as db_api
from mistral.actions import std_actions
from mistral.engine.scalable.executor import client

WORKBOOK_NAME = 'my_workbook'
TASK_NAME = 'my_task'

SAMPLE_WORKBOOK = {
    'id': str(uuid.uuid4()),
    'name': WORKBOOK_NAME,
    'description': 'my description',
    'definition': base.get_resource("test_rest.yaml"),
    'tags': [],
    'scope': 'public',
    'updated_at': None,
    'project_id': '123',
    'trust_id': '1234'
}

SAMPLE_EXECUTION = {
    'id': str(uuid.uuid4()),
    'workbook_name': WORKBOOK_NAME,
    'task': TASK_NAME,
    'state': states.RUNNING,
    'updated_at': None,
    'context': None
}

SAMPLE_TASK = {
    'name': TASK_NAME,
    'workbook_name': WORKBOOK_NAME,
    'action_spec': {
        'name': 'my-action',
        'class': 'std.http',
        'base-parameters': {
            'url': 'http://localhost:8989/v1/workbooks',
            'method': 'GET'
        },
        'namespace': 'MyRest'
    },
    'task_spec': {
        'action': 'MyRest.my-action',
        'name': TASK_NAME},
    'requires': {},
    'state': states.IDLE}

SAMPLE_CONTEXT = {
    'user': 'admin',
    'tenant': 'mistral'
}


class TestExecutor(base.DbTestCase):
    def mock_action_run(self):
        std_actions.HTTPAction.run = mock.MagicMock(return_value={})
        return std_actions.HTTPAction.run

    def setUp(self):
        super(TestExecutor, self).setUp()

        # Run the Executor in the background.
        self.transport = base.get_fake_transport()
        self.ex_thread = eventlet.spawn(launch.launch_executor, self.transport)

    def tearDown(self):
        # Stop the Executor.
        self.ex_thread.kill()

        super(TestExecutor, self).tearDown()

    def test_handle_task(self):
        # Mock HTTP action.
        mock_rest_action = self.mock_action_run()

        # Create a new workbook.
        workbook = db_api.workbook_create(SAMPLE_WORKBOOK)
        self.assertIsInstance(workbook, dict)

        # Create a new execution.
        execution = db_api.execution_create(SAMPLE_EXECUTION['workbook_name'],
                                            SAMPLE_EXECUTION)
        self.assertIsInstance(execution, dict)

        # Create a new task.
        SAMPLE_TASK['execution_id'] = execution['id']
        task = db_api.task_create(SAMPLE_TASK['workbook_name'],
                                  SAMPLE_TASK['execution_id'],
                                  SAMPLE_TASK)
        self.assertIsInstance(task, dict)
        self.assertIn('id', task)

        # Send the task request to the Executor.
        ex_client = client.ExecutorClient(self.transport)
        ex_client.handle_task(SAMPLE_CONTEXT, task=task)

        # Check task execution state. There is no timeout mechanism in
        # unittest. There is an example to add a custom timeout decorator that
        # can wrap this test function in another process and then manage the
        # process time. However, it seems more straightforward to keep the
        # loop finite.
        for i in range(0, 50):
            db_task = db_api.task_get(task['workbook_name'],
                                      task['execution_id'],
                                      task['id'])
            # Ensure the request reached the executor and the action has ran.
            if db_task['state'] != states.IDLE:
                # We have to wait sometime due to time interval between set
                # task state to RUNNING and invocation action.run()
                time.sleep(0.1)
                mock_rest_action.assert_called_once_with()
                self.assertIn(db_task['state'],
                              [states.RUNNING, states.SUCCESS, states.ERROR])
                return
            time.sleep(0.1)

        # Task is not being processed. Throw an exception here.
        raise Exception('Timed out waiting for task to be processed.')
