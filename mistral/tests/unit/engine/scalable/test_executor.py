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
import mock

from oslo.config import cfg

from mistral.tests import base
from mistral.openstack.common import log as logging
from mistral.openstack.common import importutils
from mistral.engine import states
from mistral.db import api as db_api
from mistral.actions import std_actions
from mistral.engine import client as engine
from mistral.engine.scalable.executor import client as executor


# We need to make sure that all configuration properties are registered.
importutils.import_module("mistral.config")
LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK_NAME = 'my_workbook'
TASK_NAME = 'create-vms'

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
    def __init__(self, *args, **kwargs):
        super(TestExecutor, self).__init__(*args, **kwargs)
        self.transport = base.get_fake_transport()

    @mock.patch.object(
        executor.ExecutorClient, 'handle_task',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_handle_task))
    @mock.patch.object(
        std_actions.HTTPAction, 'run', mock.MagicMock(return_value={}))
    @mock.patch.object(
        engine.EngineClient, 'convey_task_result',
        mock.MagicMock(side_effect=base.EngineTestCase.mock_task_result))
    def test_handle_task(self):
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
        ex_client = executor.ExecutorClient(self.transport)
        ex_client.handle_task(SAMPLE_CONTEXT, task=task)

        # Check task execution state.
        db_task = db_api.task_get(task['workbook_name'],
                                  task['execution_id'],
                                  task['id'])
        self.assertEqual(db_task['state'], states.SUCCESS)
