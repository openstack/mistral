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

import cachetools
import mock

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.rpc import clients as rpc_clients
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class ActionHeartbeatTest(base.EngineTestCase):
    def setUp(self):
        # We need to override configuration values before starting engine.
        self.override_config('check_interval', 1, 'action_heartbeat')
        self.override_config('max_missed_heartbeats', 1, 'action_heartbeat')
        self.override_config('first_heartbeat_timeout', 0, 'action_heartbeat')

        super(ActionHeartbeatTest, self).setUp()

    # Make sure actions are not sent to an executor.
    @mock.patch.object(
        rpc_clients.ExecutorClient,
        'run_action',
        mock.MagicMock()
    )
    def test_fail_action_with_missing_heartbeats(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        # The workflow should fail because the action of "task1" should be
        # failed automatically by the action execution heartbeat checker.
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='task1',
                state=states.ERROR
            )

            a_execs = db_api.get_action_executions(task_execution_id=t_ex.id)

            self._assert_single_item(
                a_execs,
                name='std.noop',
                state=states.ERROR
            )

    # Make sure actions are not sent to an executor.
    @mock.patch.object(
        rpc_clients.ExecutorClient,
        'run_action',
        mock.MagicMock()
    )
    @mock.patch.object(
        cachetools.LRUCache,
        '__getitem__',
        mock.MagicMock(side_effect=KeyError)
    )
    def test_fail_action_with_missing_heartbeats_wf_spec_not_cached(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        # The workflow should fail because the action of "task1" should be
        # failed automatically by the action execution heartbeat checker.
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='task1',
                state=states.ERROR
            )

            a_execs = db_api.get_action_executions(task_execution_id=t_ex.id)

            self._assert_single_item(
                a_execs,
                name='std.noop',
                state=states.ERROR
            )
