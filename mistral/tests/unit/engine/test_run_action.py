# Copyright 2015 - Mirantis, Inc.
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

import mock
from oslo_config import cfg

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.services import actions
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral.workflow import utils as wf_utils

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class RunActionEngineTest(base.EngineTestCase):
    @classmethod
    def heavy_init(cls):
        super(RunActionEngineTest, cls).heavy_init()

        action = """---
        version: '2.0'

        concat:
          base: std.echo
          base-input:
            output: <% $.left %><% $.right %>
          input:
            - left
            - right
        """
        actions.create_actions(action)

    def tearDown(self):
        super(RunActionEngineTest, self).tearDown()

    def test_run_action_sync(self):
        # Start action and see the result.
        action_ex = self.engine.start_action('std.echo', {'output': 'Hello!'})

        self.assertEqual('Hello!', action_ex.output['result'])

    @mock.patch.object(
        std_actions.EchoAction,
        'run',
        mock.Mock(side_effect=exc.ActionException("some error"))
    )
    def test_run_action_error(self):
        # Start action and see the result.
        action_ex = self.engine.start_action('std.echo', {'output': 'Hello!'})

        self.assertIn('some error', action_ex.output['result'])

    def test_run_action_save_result(self):
        # Start action.
        action_ex = self.engine.start_action(
            'std.echo',
            {'output': 'Hello!'},
            save_result=True
        )

        is_action_ex_success = (
            lambda: db_api.get_action_execution(
                action_ex.id
            ).state == states.SUCCESS
        )

        self._await(is_action_ex_success)

        action_ex = db_api.get_action_execution(action_ex.id)

        self.assertEqual(states.SUCCESS, action_ex.state)
        self.assertEqual({'result': 'Hello!'}, action_ex.output)

    def test_run_action_async(self):
        action_ex = self.engine.start_action('std.async_noop', {})

        is_action_ex_running = (
            lambda: db_api.get_action_execution(
                action_ex.id
            ).state == states.RUNNING
        )

        self._await(is_action_ex_running)

        action_ex = db_api.get_action_execution(action_ex.id)

        self.assertEqual(states.RUNNING, action_ex.state)

    @mock.patch.object(
        std_actions.AsyncNoOpAction, 'run',
        mock.MagicMock(side_effect=exc.ActionException('Invoke failed.')))
    def test_run_action_async_invoke_failure(self):
        action_ex = self.engine.start_action('std.async_noop', {})

        is_action_ex_error = (
            lambda: db_api.get_action_execution(
                action_ex.id
            ).state == states.ERROR
        )

        self._await(is_action_ex_error)

        action_ex = db_api.get_action_execution(action_ex.id)

        self.assertEqual(states.ERROR, action_ex.state)
        self.assertIn('Invoke failed.', action_ex.output.get('result', ''))

    @mock.patch.object(
        std_actions.AsyncNoOpAction, 'run',
        mock.MagicMock(return_value=wf_utils.Result(error='Invoke erred.')))
    def test_run_action_async_invoke_with_error(self):
        action_ex = self.engine.start_action('std.async_noop', {})

        is_action_ex_error = (
            lambda: db_api.get_action_execution(
                action_ex.id
            ).state == states.ERROR
        )

        self._await(is_action_ex_error)

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

    def test_run_action_wrong_input(self):
        # Start action and see the result.
        exception = self.assertRaises(
            exc.InputException,
            self.engine.start_action,
            'std.http',
            {'url': 'Hello, ', 'metod': 'John Doe!'}
        )

        self.assertIn('std.http', exception.message)

    def test_adhoc_action_wrong_input(self):
        # Start action and see the result.
        exception = self.assertRaises(
            exc.InputException,
            self.engine.start_action,
            'concat',
            {'left': 'Hello, ', 'ri': 'John Doe!'}
        )

        self.assertIn('concat', exception.message)

    @mock.patch('mistral.engine.action_handler.resolve_action_definition')
    @mock.patch('mistral.engine.utils.validate_input')
    @mock.patch('mistral.services.action_manager.get_action_class')
    @mock.patch('mistral.engine.action_handler.run_action')
    def test_run_action_with_kwargs_input(self, run_mock, class_mock,
                                          validate_mock, def_mock):
        action_def = models.ActionDefinition()
        action_def.update({
            'name': 'fake_action',
            'action_class': '',
            'attributes': {},
            'description': '',
            'input': '**kwargs',
            'is_system': True,
            'scope': 'public'
        })
        def_mock.return_value = action_def
        run_mock.return_value = {'result': 'Hello'}

        class_ret = mock.MagicMock()
        class_mock.return_value = class_ret

        self.engine.start_action('fake_action', {'input': 'Hello'})

        self.assertEqual(2, def_mock.call_count)
        def_mock.assert_called_with('fake_action', None, None)

        self.assertEqual(0, validate_mock.call_count)

        class_ret.assert_called_once_with(input='Hello')

        run_mock.assert_called_once_with(
            action_def,
            {'input': 'Hello'},
            target=None,
            async=False
        )
