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

import time

import eventlet
import mock
from oslo.config import cfg

eventlet.monkey_patch()

from mistral.actions import std_actions
from mistral.cmd import launch
from mistral.db import api as db_api
from mistral.engine import states
from mistral.openstack.common import importutils
from mistral.openstack.common import log as logging
from mistral.tests import base


# We need to make sure that all configuration properties are registered.
importutils.import_module("mistral.config")
LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WB_NAME = 'my_workbook'
CONTEXT = None  # TODO(rakhmerov): Use a meaningful value.


class TestTransport(base.EngineTestCase):
    def setUp(self):
        super(TestTransport, self).setUp()

        # Run the Engine and Executor in the background.
        self.en_thread = eventlet.spawn(launch.launch_engine, self.transport)
        self.addCleanup(self.en_thread.kill)
        self.ex_thread = eventlet.spawn(launch.launch_executor, self.transport)
        self.addCleanup(self.ex_thread.kill)

    @mock.patch.object(
        db_api, 'workbook_get',
        mock.MagicMock(
            return_value={'definition': base.get_resource('test_rest.yaml')}))
    @mock.patch.object(
        std_actions.HTTPAction, 'run', mock.MagicMock(return_value={}))
    def test_transport(self):
        """Test if engine request traversed through the oslo.messaging
        transport.
        """
        execution = self.engine.start_workflow_execution(
            WB_NAME, 'create-vms', CONTEXT)

        task = db_api.tasks_get(workbook_name=WB_NAME,
                                execution_id=execution['id'])[0]

        # Check task execution state. There is no timeout mechanism in
        # unittest. There is an example to add a custom timeout decorator that
        # can wrap this test function in another process and then manage the
        # process time. However, it seems more straightforward to keep the
        # loop finite.
        for i in range(0, 50):
            db_task = db_api.task_get(task['id'])
            # Ensure the request reached the executor and the action has ran.
            if db_task['state'] != states.IDLE:
                # We have to wait sometime due to time interval between set
                # task state to RUNNING and invocation action.run()
                time.sleep(0.1)
                self.assertIn(db_task['state'],
                              [states.RUNNING, states.SUCCESS, states.ERROR])
                return
            time.sleep(0.1)

        # Task is not being processed. Throw an exception here.
        raise Exception('Timed out waiting for task to be processed.')
