# Copyright 2015 - Mirantis, Inc.
# Copyright 2020 Nokia Software.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from unittest import mock

from oslo_config import cfg

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import adhoc_actions
from mistral.tests.unit.engine import base
from mistral.workflow import states

from mistral_lib import actions as ml_actions
from mistral_lib import exceptions as ml_exc

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class RunActionEngineTest(base.EngineTestCase):
    def setUp(self):
        super(RunActionEngineTest, self).setUp()

        action = """---
        version: '2.0'

        concat:
          base: std.echo
          base-input:
            output: <% $.left %><% $.right %>
          input:
            - left
            - right

        concat3:
          base: concat
          base-input:
            left: <% $.left %><% $.center %>
            right: <% $.right %>
          input:
            - left
            - center
            - right

        concat4:
          base: concat3
          base-input:
            left: <% $.left %>
            center: <% $.center_left %><% $.center_right %>
            right: <% $.right %>
          input:
            - left
            - center_left
            - center_right
            - right

        missing_base:
          base: wrong
          input:
            - some_input

        nested_missing_base:
          base: missing_base
          input:
            - some_input

        loop_action:
          base: loop_action
          base-input:
            output: <% $.output %>
          input:
            - output

        level2_loop_action:
          base: loop_action
          base-input:
            output: <% $.output %>
          input:
            - output
        """

        adhoc_actions.create_actions(action)

    def test_run_action_sync(self):
        # Start action and see the result.
        action_ex = self.engine.start_action('std.echo', {'output': 'Hello!'})

        self.assertEqual('Hello!', action_ex.output['result'])
        self.assertEqual(states.SUCCESS, action_ex.state)

    def test_run_action_with_namespace(self):
        namespace = 'test_ns'

        action_text = """---
        version: '2.0'

        concat1:
          base: std.echo
          base-input:
            output: <% $.left %><% $.right %>
          input:
            - left
            - right

        concat2:
          base: concat1
          base-input:
            left: <% $.left %><% $.center %>
            right: <% $.right %>
          input:
            - left
            - center
            - right
        """

        adhoc_actions.create_actions(action_text, namespace=namespace)

        self.assertRaises(
            exc.InvalidActionException,
            self.engine.start_action,
            'concat1',
            {
                'left': 'Hello, ',
                'right': 'John Doe!'
            },
            save_result=True,
            namespace=''
        )

        action_ex = self.engine.start_action(
            'concat1',
            {
                'left': 'Hello, ',
                'right': 'John Doe!'
            },
            save_result=True,
            namespace=namespace
        )

        self.assertEqual(namespace, action_ex.workflow_namespace)

        self.await_action_success(action_ex.id)

        with db_api.transaction():
            action_ex = db_api.get_action_execution(action_ex.id)

            self.assertEqual(states.SUCCESS, action_ex.state)
            self.assertEqual({'result': u'Hello, John Doe!'}, action_ex.output)

        action_ex = self.engine.start_action(
            'concat2',
            {
                'left': 'Hello, ',
                'center': 'John',
                'right': ' Doe!'
            },
            save_result=True,
            namespace=namespace
        )

        self.assertEqual(namespace, action_ex.workflow_namespace)

        self.await_action_success(action_ex.id)

        with db_api.transaction():
            action_ex = db_api.get_action_execution(action_ex.id)

            self.assertEqual(states.SUCCESS, action_ex.state)
            self.assertEqual('Hello, John Doe!', action_ex.output['result'])

    def test_run_action_with_invalid_namespace(self):
        # This test checks the case in which, the action with that name is
        # not found with the given name, if an action was found with the
        # same name in default namespace, that action will run.

        action_ex = self.engine.start_action(
            'concat',
            {'left': 'Hello, ', 'right': 'John Doe!'},
            save_result=True,
            namespace='namespace'
        )

        self.assertIsNotNone(action_ex)

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.Mock(side_effect=exc.ActionException("some error"))
    )
    def test_run_action_error(self):
        # Start action and see the result.
        action_ex = self.engine.start_action('std.echo', {'output': 'Hello!'})

        self.assertIsNotNone(action_ex.output)
        self.assertIn('some error', action_ex.output['result'])
        self.assertEqual(states.ERROR, action_ex.state)

    def test_run_action_save_result(self):
        # Start action.
        action_ex = self.engine.start_action(
            'std.echo',
            {'output': 'Hello!'},
            save_result=True
        )

        self.await_action_success(action_ex.id)

        with db_api.transaction():
            action_ex = db_api.get_action_execution(action_ex.id)

            self.assertEqual(states.SUCCESS, action_ex.state)
            self.assertEqual({'result': 'Hello!'}, action_ex.output)

    def test_run_action_run_sync(self):
        # Start action.
        action_ex = self.engine.start_action(
            'std.echo',
            {'output': 'Hello!'},
            run_sync=True
        )

        self.assertEqual('Hello!', action_ex.output['result'])
        self.assertEqual(states.SUCCESS, action_ex.state)

    def test_run_action_save_result_and_run_sync(self):
        # Start action.
        action_ex = self.engine.start_action(
            'std.echo',
            {'output': 'Hello!'},
            save_result=True,
            run_sync=True
        )

        self.assertEqual('Hello!', action_ex.output['result'])
        self.assertEqual(states.SUCCESS, action_ex.state)

        with db_api.transaction():
            action_ex = db_api.get_action_execution(action_ex.id)

            self.assertEqual(states.SUCCESS, action_ex.state)
            self.assertEqual({'result': 'Hello!'}, action_ex.output)

    def test_run_action_run_sync_error(self):
        # Start action.
        self.assertRaises(
            exc.InputException,
            self.engine.start_action,
            'std.async_noop',
            {},
            run_sync=True
        )

    def test_run_action_async(self):
        action_ex = self.engine.start_action('std.async_noop', {})

        self.await_action_state(action_ex.id, states.RUNNING)

        action_ex = db_api.get_action_execution(action_ex.id)

        self.assertEqual(states.RUNNING, action_ex.state)

    @mock.patch.object(
        std_actions.AsyncNoOpAction, 'run',
        mock.MagicMock(side_effect=exc.ActionException('Invoke failed.')))
    def test_run_action_async_invoke_failure(self):
        action_ex = self.engine.start_action('std.async_noop', {})

        self.await_action_error(action_ex.id)

        with db_api.transaction():
            action_ex = db_api.get_action_execution(action_ex.id)

            self.assertEqual(states.ERROR, action_ex.state)
            self.assertIn('Invoke failed.', action_ex.output.get('result', ''))

    @mock.patch.object(
        std_actions.AsyncNoOpAction, 'run',
        mock.MagicMock(return_value=ml_actions.Result(error='Invoke erred.')))
    def test_run_action_async_invoke_with_error(self):
        action_ex = self.engine.start_action('std.async_noop', {})

        self.await_action_error(action_ex.id)

        with db_api.transaction():
            action_ex = db_api.get_action_execution(action_ex.id)

            self.assertEqual(states.ERROR, action_ex.state)
            self.assertIn('Invoke erred.', action_ex.output.get('result', ''))

    def test_run_action_adhoc(self):
        # Start action and see the result.
        action_ex = self.engine.start_action(
            'concat',
            {'left': 'Hello, ', 'right': 'John Doe!'}
        )

        self.assertEqual('Hello, John Doe!', action_ex.output['result'])

    def test_run_level_two_action_adhoc(self):
        # Start action and see the result.
        action_ex = self.engine.start_action(
            'concat3',
            {'left': 'Hello, ', 'center': 'John', 'right': ' Doe!'}
        )

        self.assertEqual('Hello, John Doe!', action_ex.output['result'])

    def test_run_level_three_action_adhoc(self):
        # Start action and see the result.
        action_ex = self.engine.start_action(
            'concat4',
            {
                'left': 'Hello, ',
                'center_left': 'John',
                'center_right': ' Doe',
                'right': '!'
            }
        )

        self.assertEqual('Hello, John Doe!', action_ex.output['result'])

    def test_run_action_with_missing_base(self):
        # Start action and see the result.
        self.assertRaises(
            exc.InvalidActionException,
            self.engine.start_action,
            'missing_base',
            {'some_input': 'Hi'}
        )

    def test_run_action_with_missing_nested_base(self):
        # Start action and see the result.
        self.assertRaises(
            exc.InvalidActionException,
            self.engine.start_action,
            'nested_missing_base',
            {'some_input': 'Hi'}
        )

    def test_run_loop_action(self):
        # Start action and see the result.
        self.assertRaises(
            ValueError,
            self.engine.start_action,
            'loop_action',
            {'output': 'Hello'}
        )

    def test_run_level_two_loop_action(self):
        # Start action and see the result.
        self.assertRaises(
            ValueError,
            self.engine.start_action,
            'level2_loop_action',
            {'output': 'Hello'}
        )

    def test_run_action_wrong_input(self):
        # Start action and see the result.
        exception = self.assertRaises(
            ml_exc.ActionException,
            self.engine.start_action,
            'std.http',
            {'url': 'Hello, ', 'metod': 'John Doe!'}
        )

        self.assertIn('std.http', str(exception))

    def test_adhoc_action_wrong_input(self):
        # Start action and see the result.
        exception = self.assertRaises(
            ml_exc.ActionException,
            self.engine.start_action,
            'concat',
            {'left': 'Hello, ', 'ri': 'John Doe!'}
        )

        self.assertIn('concat', str(exception))

    def test_run_action_with_kwargs_input(self):
        class FakeAction(ml_actions.Action):
            def __init__(self, **kwargs):
                super(FakeAction, self).__init__()

                self.kwargs = kwargs

            def run(self, context):
                return ml_actions.Result(data=self.kwargs)

        self.register_action_class('fake_action', FakeAction)

        action_ex = self.engine.start_action(
            'fake_action',
            {'param1': 'Hello'}
        )

        self.assertDictEqual({'param1': 'Hello'}, action_ex.input)
