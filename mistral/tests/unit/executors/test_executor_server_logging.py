# Copyright 2026 - OVHcloud.
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

from unittest import mock

from mistral.actions import std_actions as std
from mistral.executors import executor_server
from mistral.tests.unit import base


class ExecutorServerLoggingTest(base.BaseTest):
    """run_action must log the action by name, not by object repr.

    Logging the action object rendered the useless default repr
    (``<...NoOpAction object at 0x...>``); log its class name instead.
    """

    @mock.patch('mistral.executors.executor_server.LOG')
    def test_run_action_logs_action_class_name(self, mock_log):
        srv = executor_server.ExecutorServer(
            mock.Mock(), setup_profiler=False
        )

        rpc_ctx = mock.Mock()
        rpc_ctx.redelivered = False

        srv.run_action(rpc_ctx, std.NoOpAction(), 'ax-1', False, {}, None)

        logged = ' '.join(
            str(a)
            for call in mock_log.debug.call_args_list
            for a in call.args
        )
        self.assertIn('NoOpAction', logged)
        # The unhelpful default object repr must not appear.
        self.assertNotIn('object at 0x', logged)
        self.assertNotIn('<mistral', logged)
