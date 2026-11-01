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

import threading
import time
from unittest import mock

from mistral import context
from mistral.executors import default_executor as d_exe
from mistral.services import action_heartbeat_sender
from mistral.tests.unit import base


class BlockingAction(object):
    def __init__(self):
        self.release = threading.Event()
        self.started = threading.Event()
        self.thread = None

    def run(self, ctx):
        self.thread = threading.current_thread()
        self.started.set()
        self.release.wait()

        return 'late result'

    def is_sync(self):
        return True


class FastAction(BlockingAction):
    def run(self, ctx):
        return 'result'


@mock.patch.object(action_heartbeat_sender, 'add_action', mock.Mock())
@mock.patch.object(action_heartbeat_sender, 'remove_action', mock.Mock())
@mock.patch.object(context, 'ctx', mock.Mock(return_value=None))
class DefaultExecutorTimeoutTest(base.BaseTest):
    def setUp(self):
        super(DefaultExecutorTimeoutTest, self).setUp()

        self.engine_client = mock.Mock()
        patcher = mock.patch.object(
            d_exe.rpc, 'get_engine_client', return_value=self.engine_client
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.executor = d_exe.DefaultExecutor()

        # Threads abandoned by other tests still update the shared counter.
        self._await(
            lambda: d_exe._abandoned_count == 0, delay=0.05, timeout=10
        )

    def _blocking_action(self):
        action = BlockingAction()

        def _release():
            action.release.set()

            if action.started.wait(5):
                action.thread.join(5)

        self.addCleanup(_release)

        return action, _release

    def test_timed_out_action_is_abandoned(self):
        action, _ = self._blocking_action()

        start = time.monotonic()

        self.executor.run_action(action, 'ex-id', False, {}, timeout=0.2)

        self.assertLess(time.monotonic() - start, 5)

        self.engine_client.on_action_complete.assert_called_once()
        ex_id, result = self.engine_client.on_action_complete.call_args[0]

        self.assertEqual('ex-id', ex_id)
        self.assertTrue(result.is_error())
        self.assertIn('Timeout after 0.2 seconds', result.error)

    def test_timed_out_action_late_result_is_ignored(self):
        action, _ = self._blocking_action()

        result = self.executor.run_action(action, None, False, {}, timeout=0.2)

        self.assertTrue(result.is_error())
        self.assertTrue(action.started.wait(5))
        self.assertTrue(action.thread.daemon)
        self.assertTrue(action.thread.is_alive())

        action.release.set()
        action.thread.join(5)

        self.assertFalse(action.thread.is_alive())
        self.assertTrue(result.is_error())
        self.engine_client.on_action_complete.assert_not_called()

    def test_action_within_timeout(self):
        result = self.executor.run_action(
            FastAction(), None, False, {}, timeout=5
        )

        self.assertFalse(result.is_error())
        self.assertEqual('result', result.data)

    def _abandon_action(self):
        action, _release = self._blocking_action()

        self.executor.run_action(action, None, False, {}, timeout=0.1)

        return action, _release

    def test_abandoned_threads_are_counted(self):
        action, release = self._abandon_action()

        self.assertEqual(1, d_exe._abandoned_count)

        release()

        self.assertFalse(action.thread.is_alive())
        self.assertEqual(0, d_exe._abandoned_count)

    def test_abandoned_threads_limit(self):
        self.override_config('max_abandoned_action_threads', 1, 'executor')

        _, release = self._abandon_action()

        self.executor.run_action(FastAction(), 'ex-id', False, {}, timeout=5)

        self.engine_client.on_action_complete.assert_called_once()
        ex_id, result = self.engine_client.on_action_complete.call_args[0]

        self.assertEqual('ex-id', ex_id)
        self.assertTrue(result.is_error())
        self.assertIn('abandoned timed-out action threads', result.error)

        release()

        result = self.executor.run_action(
            FastAction(), None, False, {}, timeout=5
        )

        self.assertFalse(result.is_error())
        self.assertEqual('result', result.data)

    def test_abandoned_threads_unlimited(self):
        self.override_config('max_abandoned_action_threads', 0, 'executor')

        self._abandon_action()
        self._abandon_action()

        result = self.executor.run_action(
            FastAction(), None, False, {}, timeout=5
        )

        self.assertFalse(result.is_error())
