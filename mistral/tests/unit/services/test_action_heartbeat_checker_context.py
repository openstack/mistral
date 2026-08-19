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

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import action_heartbeat_checker
from mistral.tests.unit import base


def _action_ex_mock(action_ex_id, task_ex_id):
    action_ex = mock.MagicMock()
    action_ex.id = action_ex_id
    action_ex.task_execution_id = task_ex_id

    return action_ex


class ActionHeartbeatCheckerContextTest(base.DbTestCase):
    """Checks the security context handling of the heartbeat checker.

    The checker thread runs with an administrative context. Processing
    an expired action must not replace it with a non-admin project-less
    context, otherwise the DB lookups of the next actions of the batch
    become project-scoped and fail with DBEntityNotFoundError, rolling
    back the whole batch (and the checker retries the same batch
    forever).
    """

    def setUp(self):
        super(ActionHeartbeatCheckerContextTest, self).setUp()

        auth_ctx.set_ctx(
            auth_ctx.MistralContext(
                user_id=None,
                project_id=None,
                auth_token=None,
                is_admin=True
            )
        )

        self.addCleanup(auth_ctx.set_ctx, None)

    @mock.patch.object(action_heartbeat_checker, 'action_handler')
    @mock.patch.object(db_api, 'get_workflow_execution')
    @mock.patch.object(db_api, 'get_task_execution')
    @mock.patch.object(db_api, 'get_running_expired_sync_action_executions')
    def test_context_stays_admin_across_the_batch(
            self, get_expired_mock, get_task_mock, get_wf_mock,
            action_handler_mock):
        get_expired_mock.return_value = [
            _action_ex_mock('a_ex_1', 't_ex_1'),
            _action_ex_mock('a_ex_2', 't_ex_2')
        ]

        lookup_ctx_admin_flags = []

        def _get_task_execution(id, fields=()):
            lookup_ctx_admin_flags.append(auth_ctx.ctx().is_admin)

            task_ex = mock.MagicMock()
            task_ex.workflow_execution_id = 'wf_ex_%s' % id

            return task_ex

        get_task_mock.side_effect = _get_task_execution

        wf_ex = mock.MagicMock()
        wf_ex.id = 'wf_ex_1'
        wf_ex.root_execution_id = None

        get_wf_mock.return_value = wf_ex

        action_heartbeat_checker.handle_expired_actions()

        # Every task execution lookup must have run with an admin
        # context, including the ones after an action was processed.
        self.assertEqual([True, True], lookup_ctx_admin_flags)

        self.assertEqual(
            2,
            action_handler_mock.on_action_complete.call_count
        )

        # The thread context must still be administrative for the
        # next iterations of the checker loop.
        self.assertTrue(auth_ctx.ctx().is_admin)

    @mock.patch.object(action_heartbeat_checker, 'action_handler')
    @mock.patch.object(db_api, 'get_workflow_execution')
    @mock.patch.object(db_api, 'get_task_execution')
    @mock.patch.object(db_api, 'get_running_expired_sync_action_executions')
    def test_missing_task_execution_does_not_abort_the_batch(
            self, get_expired_mock, get_task_mock, get_wf_mock,
            action_handler_mock):
        get_expired_mock.return_value = [
            _action_ex_mock('a_ex_1', 't_ex_1'),
            _action_ex_mock('a_ex_2', 't_ex_2')
        ]

        task_ex = mock.MagicMock()
        task_ex.workflow_execution_id = 'wf_ex_2'

        get_task_mock.side_effect = [
            exc.DBEntityNotFoundError(
                "Task execution not found [id=t_ex_1]"
            ),
            task_ex
        ]

        wf_ex = mock.MagicMock()
        wf_ex.id = 'wf_ex_2'
        wf_ex.root_execution_id = None

        get_wf_mock.return_value = wf_ex

        action_heartbeat_checker.handle_expired_actions()

        # The first action is skipped but the second one is processed.
        self.assertEqual(
            1,
            action_handler_mock.on_action_complete.call_count
        )

        processed_action_ex = (
            action_handler_mock.on_action_complete.call_args[0][0]
        )

        self.assertEqual('a_ex_2', processed_action_ex.id)
