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

from oslo import messaging
from oslo.config import cfg

from mistral.tests import base
from mistral.engine import states
from mistral.db import api as db_api
from mistral.engine.actions import actions
from mistral.engine.actions import action_types
from mistral.engine.scalable.executor import server
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
    'service_spec': {
        'type': action_types.REST_API,
        'parameters': {
            'baseUrl': 'http://localhost:8989/v1/'},
        'actions': {
            'my-action': {
                'parameters': {
                    'url': 'workbooks',
                    'method': 'GET'}}},
        'name': 'MyService'
    },
    'task_spec': {
        'action': 'MyRest:my-action',
        'service_name': 'MyRest',
        'name': TASK_NAME},
    'requires': {},
    'state': states.IDLE}


SAMPLE_CONTEXT = {
    'user': 'admin',
    'tenant': 'mistral'
}


class TestExecutor(base.DbTestCase):

    def get_transport(self):
        # Get transport manually, oslo.messaging get_transport seems broken.
        from stevedore import driver
        from oslo.messaging import transport
        # Get transport here to let oslo.messaging setup default config before
        # changing the rpc_backend to the fake driver; otherwise,
        # oslo.messaging will throw exception.
        messaging.get_transport(cfg.CONF)
        cfg.CONF.set_default('rpc_backend', 'fake')
        url = transport.TransportURL.parse(cfg.CONF, None, None)
        kwargs = dict(default_exchange=cfg.CONF.control_exchange,
                      allowed_remote_exmods=[])
        mgr = driver.DriverManager('oslo.messaging.drivers',
                                   url.transport,
                                   invoke_on_load=True,
                                   invoke_args=[cfg.CONF, url],
                                   invoke_kwds=kwargs)
        return transport.Transport(mgr.driver)

    def mock_action_run(self):
        actions.RestAction.run = mock.MagicMock(return_value={})
        return actions.RestAction.run

    def setUp(self):
        # Initialize configuration for the ExecutorClient.
        super(TestExecutor, self).setUp()
        if not 'executor' in cfg.CONF:
            cfg_grp = cfg.OptGroup(name='executor', title='Executor options')
            opts = [cfg.StrOpt('host', default='0.0.0.0'),
                    cfg.StrOpt('topic', default='executor')]
            cfg.CONF.register_group(cfg_grp)
            cfg.CONF.register_opts(opts, group=cfg_grp)

        # Start the Executor.
        transport = self.get_transport()
        target = messaging.Target(topic='executor', server='0.0.0.0')
        endpoints = [server.Executor()]
        self.server = messaging.get_rpc_server(transport, target,
                                               endpoints, executor='eventlet')
        self.server.start()

    def tearDown(self):
        # Stop the Executor.
        if self.server:
            self.server.stop()

        super(TestExecutor, self).tearDown()

    def test_handle_task(self):
        # Mock the RestAction
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
        transport = self.server.transport
        ex_client = client.ExecutorClient(transport)
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
                mock_rest_action.assert_called_once_with()
                self.assertIn(db_task['state'],
                              [states.RUNNING, states.SUCCESS, states.ERROR])
                return
            time.sleep(0.1)

        # Task is not being processed. Throw an exception here.
        raise Exception('Timed out waiting for task to be processed.')
