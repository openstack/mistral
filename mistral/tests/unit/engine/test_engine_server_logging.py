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

from mistral.engine import engine_server
from mistral.tests.unit import base

# A recognizable secret; a std.ssh* action carries these in its input.
SECRET_KEY = '-----BEGIN OPENSSH PRIVATE KEY-----SECRETKEYMATERIAL'
SECRET_PWD = 'hunter2-super-secret'


class EngineServerLoggingTest(base.BaseTest):
    """The engine RPC server must not log user-supplied secrets.

    A std.ssh / std.ssh_proxied action input carries a private_key (and
    possibly a password); it must be redacted before it is written to the
    engine logs, while the engine itself still receives the real input.
    """

    def _server(self):
        return engine_server.EngineServer(mock.Mock(), setup_profiler=False)

    @staticmethod
    def _logged(mock_log):
        # Render every positional argument passed to LOG.info to a string.
        return ' '.join(str(a) for a in mock_log.info.call_args.args)

    @mock.patch('mistral.engine.engine_server.LOG')
    def test_start_action_logs_only_name(self, mock_log):
        srv = self._server()

        action_input = {
            'cmd': 'true',
            'host': '127.0.0.1',
            'private_key': SECRET_KEY,
            'password': SECRET_PWD,
        }

        srv.start_action(
            mock.Mock(),
            'std.ssh_proxied',
            action_input,
            '',
            '',
            {}
        )

        logged = self._logged(mock_log)
        # Only the action name is logged; the input is not, so no secret
        # (nor any other input value) can reach the log.
        self.assertIn('std.ssh_proxied', logged)
        self.assertNotIn(SECRET_KEY, logged)
        self.assertNotIn(SECRET_PWD, logged)
        self.assertNotIn('127.0.0.1', logged)
        self.assertNotIn('input=', logged)

        # The engine still receives the real, unredacted input.
        srv.engine.start_action.assert_called_once()
        self.assertEqual(
            SECRET_KEY,
            srv.engine.start_action.call_args.args[1]['private_key']
        )

    @mock.patch('mistral.engine.engine_server.LOG')
    def test_start_workflow_logs_identifier_and_description(self, mock_log):
        srv = self._server()

        srv.start_workflow(
            mock.Mock(),
            'my_wf',
            '',
            None,
            {'private_key': SECRET_KEY},
            'a human description',
            {'env': {'password': SECRET_PWD}}
        )

        logged = self._logged(mock_log)
        # The identifier and the (non-sensitive) description are logged;
        # the input and params are not, so no secret can reach the log.
        self.assertIn('my_wf', logged)
        self.assertIn('a human description', logged)
        self.assertNotIn(SECRET_KEY, logged)
        self.assertNotIn(SECRET_PWD, logged)
        self.assertNotIn('workflow_input=', logged)
        self.assertNotIn('params=', logged)

        # The engine still receives the real, unredacted input.
        srv.engine.start_workflow.assert_called_once()
        self.assertEqual(
            SECRET_KEY,
            srv.engine.start_workflow.call_args.args[3]['private_key']
        )

    @mock.patch('mistral.engine.engine_server.LOG')
    def test_on_action_complete_logs_only_id(self, mock_log):
        srv = self._server()

        # An action result can carry secrets; cut_repr() only masks known
        # key names, so the result must not be logged at all.
        result = mock.Mock()
        result.cut_repr.return_value = 'RESULT-CARRYING-' + SECRET_PWD

        srv.on_action_complete(mock.Mock(), 'action-ex-123', result, False)

        logged = self._logged(mock_log)
        self.assertIn('action-ex-123', logged)
        self.assertNotIn(SECRET_PWD, logged)
        self.assertNotIn('result=', logged)
        # The result is never rendered into the log.
        result.cut_repr.assert_not_called()

        # The engine still receives the real result.
        srv.engine.on_action_complete.assert_called_once()
        self.assertIs(
            result,
            srv.engine.on_action_complete.call_args.args[1]
        )
