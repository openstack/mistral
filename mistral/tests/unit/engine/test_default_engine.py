# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

import datetime
import uuid

import mock
from oslo_config import cfg
from oslo_messaging.rpc import client as rpc_client

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine import default_engine as d_eng
from mistral import exceptions as exc
from mistral.services import workbooks as wb_service
from mistral.tests.unit import base
from mistral.tests.unit.engine import base as eng_test_base
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
version: '2.0'

name: wb

workflows:
  wf:
    type: reverse
    input:
      - param1: value1
      - param2

    tasks:
      task1:
        action: std.echo output=<% $.param1 %>
        publish:
            var: <% task(task1).result %>

      task2:
        action: std.echo output=<% $.param2 %>
        requires: [task1]

"""

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

ENVIRONMENT = {
    'id': str(uuid.uuid4()),
    'name': 'test',
    'description': 'my test settings',
    'variables': {
        'key1': 'abc',
        'key2': 123
    },
    'scope': 'private',
    'created_at': str(datetime.datetime.utcnow()),
    'updated_at': str(datetime.datetime.utcnow())
}

ENVIRONMENT_DB = models.Environment(
    id=ENVIRONMENT['id'],
    name=ENVIRONMENT['name'],
    description=ENVIRONMENT['description'],
    variables=ENVIRONMENT['variables'],
    scope=ENVIRONMENT['scope'],
    created_at=datetime.datetime.strptime(ENVIRONMENT['created_at'],
                                          DATETIME_FORMAT),
    updated_at=datetime.datetime.strptime(ENVIRONMENT['updated_at'],
                                          DATETIME_FORMAT)
)

MOCK_ENVIRONMENT = mock.MagicMock(return_value=ENVIRONMENT_DB)
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())


class DefaultEngineTest(base.DbTestCase):
    def setUp(self):
        super(DefaultEngineTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK)

        # Note: For purposes of this test we can easily use
        # simple magic mocks for engine and executor clients
        self.engine = d_eng.DefaultEngine(mock.MagicMock())

    def test_start_workflow(self):
        wf_input = {'param1': 'Hey', 'param2': 'Hi'}

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            wf_input,
            'my execution',
            task_name='task2'
        )

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual('my execution', wf_ex.description)
        self.assertIn('__execution', wf_ex.context)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))

        task_ex = wf_ex.task_executions[0]

        self.assertEqual('wb.wf', task_ex.workflow_name)
        self.assertEqual('task1', task_ex.name)
        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertIsNotNone(task_ex.spec)
        self.assertDictEqual({}, task_ex.runtime_context)

        # Data Flow properties.
        action_execs = db_api.get_action_executions(
            task_execution_id=task_ex.id
        )

        self.assertEqual(1, len(action_execs))

        task_action_ex = action_execs[0]

        self.assertIsNotNone(task_action_ex)
        self.assertDictEqual({'output': 'Hey'}, task_action_ex.input)

    def test_start_workflow_with_input_default(self):
        wf_input = {'param2': 'value2'}

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            wf_input,
            task_name='task1'
        )

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertIn('__execution', wf_ex.context)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))

        task_ex = wf_ex.task_executions[0]

        self.assertEqual('wb.wf', task_ex.workflow_name)
        self.assertEqual('task1', task_ex.name)
        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertIsNotNone(task_ex.spec)
        self.assertDictEqual({}, task_ex.runtime_context)

        # Data Flow properties.
        action_execs = db_api.get_action_executions(
            task_execution_id=task_ex.id
        )

        self.assertEqual(1, len(action_execs))

        task_action_ex = action_execs[0]

        self.assertIsNotNone(task_action_ex)
        self.assertDictEqual({'output': 'value1'}, task_action_ex.input)

    def test_start_workflow_with_adhoc_env(self):
        wf_input = {
            'param1': '<% env().key1 %>',
            'param2': '<% env().key2 %>'
        }
        env = ENVIRONMENT['variables']

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            wf_input,
            env=env,
            task_name='task2')

        self.assertIsNotNone(wf_ex)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertDictEqual(wf_ex.params.get('env', {}), env)

    @mock.patch.object(db_api, "load_environment", MOCK_ENVIRONMENT)
    def test_start_workflow_with_saved_env(self):
        wf_input = {
            'param1': '<% env().key1 %>',
            'param2': '<% env().key2 %>'
        }
        env = ENVIRONMENT['variables']

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            wf_input,
            env='test',
            task_name='task2'
        )

        self.assertIsNotNone(wf_ex)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertDictEqual(wf_ex.params.get('env', {}), env)

    @mock.patch.object(db_api, "get_environment", MOCK_NOT_FOUND)
    def test_start_workflow_env_not_found(self):
        e = self.assertRaises(
            exc.InputException,
            self.engine.start_workflow,
            'wb.wf',
            {
                'param1': '<% env().key1 %>',
                'param2': 'some value'
            },
            env='foo',
            task_name='task2'
        )

        self.assertEqual("Environment is not found: foo", e.message)

    def test_start_workflow_with_env_type_error(self):
        e = self.assertRaises(
            exc.InputException,
            self.engine.start_workflow,
            'wb.wf',
            {
                'param1': '<% env().key1 %>',
                'param2': 'some value'
            },
            env=True,
            task_name='task2'
        )

        self.assertIn(
            'Unexpected value type for environment',
            e.message
        )

    def test_start_workflow_missing_parameters(self):
        e = self.assertRaises(
            exc.InputException,
            self.engine.start_workflow,
            'wb.wf',
            None,
            task_name='task2'
        )

        self.assertIn("Invalid input", e.message)
        self.assertIn("missing=['param2']", e.message)

    def test_start_workflow_unexpected_parameters(self):
        e = self.assertRaises(
            exc.InputException,
            self.engine.start_workflow,
            'wb.wf',
            {
                'param1': 'Hey',
                'param2': 'Hi',
                'unexpected_param': 'val'
            },
            task_name='task2'
        )

        self.assertIn("Invalid input", e.message)
        self.assertIn("unexpected=['unexpected_param']", e.message)

    def test_on_action_complete(self):
        wf_input = {'param1': 'Hey', 'param2': 'Hi'}

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            wf_input,
            task_name='task2'
        )

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex.state)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))

        task1_ex = wf_ex.task_executions[0]

        self.assertEqual('task1', task1_ex.name)
        self.assertEqual(states.RUNNING, task1_ex.state)
        self.assertIsNotNone(task1_ex.spec)
        self.assertDictEqual({}, task1_ex.runtime_context)
        self.assertNotIn('__execution', task1_ex.in_context)

        action_execs = db_api.get_action_executions(
            task_execution_id=task1_ex.id
        )

        self.assertEqual(1, len(action_execs))

        task1_action_ex = action_execs[0]

        self.assertIsNotNone(task1_action_ex)
        self.assertDictEqual({'output': 'Hey'}, task1_action_ex.input)

        # Finish action of 'task1'.
        task1_action_ex = self.engine.on_action_complete(
            task1_action_ex.id,
            wf_utils.Result(data='Hey')
        )

        self.assertIsInstance(task1_action_ex, models.ActionExecution)
        self.assertEqual('std.echo', task1_action_ex.name)
        self.assertEqual(states.SUCCESS, task1_action_ex.state)

        # Data Flow properties.
        task1_ex = db_api.get_task_execution(task1_ex.id)  # Re-read the state.

        self.assertDictEqual({'var': 'Hey'}, task1_ex.published)
        self.assertDictEqual({'output': 'Hey'}, task1_action_ex.input)
        self.assertDictEqual({'result': 'Hey'}, task1_action_ex.output)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex.state)

        self.assertEqual(2, len(wf_ex.task_executions))

        task2_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task2'
        )

        self.assertEqual(states.RUNNING, task2_ex.state)

        action_execs = db_api.get_action_executions(
            task_execution_id=task2_ex.id
        )

        self.assertEqual(1, len(action_execs))

        task2_action_ex = action_execs[0]

        self.assertIsNotNone(task2_action_ex)
        self.assertDictEqual({'output': 'Hi'}, task2_action_ex.input)

        # Finish 'task2'.
        task2_action_ex = self.engine.on_action_complete(
            task2_action_ex.id,
            wf_utils.Result(data='Hi')
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIsNotNone(wf_ex)

        # Workflow completion check is done separate with scheduler
        # but scheduler doesn't start in this test (in fact, it's just
        # a DB test)so the workflow is expected to be in running state.
        self.assertEqual(states.RUNNING, wf_ex.state)

        self.assertIsInstance(task2_action_ex, models.ActionExecution)
        self.assertEqual('std.echo', task2_action_ex.name)
        self.assertEqual(states.SUCCESS, task2_action_ex.state)

        # Data Flow properties.
        self.assertDictEqual({'output': 'Hi'}, task2_action_ex.input)
        self.assertDictEqual({}, task2_ex.published)
        self.assertDictEqual({'output': 'Hi'}, task2_action_ex.input)
        self.assertDictEqual({'result': 'Hi'}, task2_action_ex.output)

        self.assertEqual(2, len(wf_ex.task_executions))

        self._assert_single_item(wf_ex.task_executions, name='task1')
        self._assert_single_item(wf_ex.task_executions, name='task2')

    def test_stop_workflow_fail(self):
        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            {
                'param1': 'Hey',
                'param2': 'Hi'
            },
            task_name="task2"
        )

        # Re-read execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.engine.stop_workflow(wf_ex.id, 'ERROR', "Stop this!")

        # Re-read from DB again
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual('ERROR', wf_ex.state)
        self.assertEqual("Stop this!", wf_ex.state_info)

    def test_stop_workflow_succeed(self):
        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            {
                'param1': 'Hey',
                'param2': 'Hi'
            },
            task_name="task2"
        )

        # Re-read execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.engine.stop_workflow(wf_ex.id, 'SUCCESS', "Like this, done")

        # Re-read from DB again
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual('SUCCESS', wf_ex.state)
        self.assertEqual("Like this, done", wf_ex.state_info)

    def test_stop_workflow_bad_status(self):
        wf_ex = self.engine.start_workflow(
            'wb.wf',
            {
                'param1': 'Hey',
                'param2': 'Hi'
            },
            task_name="task2"
        )

        # Re-read execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertNotEqual(
            'PAUSE',
            self.engine.stop_workflow(wf_ex.id, 'PAUSE')
        )

    def test_resume_workflow(self):
        # TODO(akhmerov): Implement.
        pass


class DefaultEngineWithTransportTest(eng_test_base.EngineTestCase):
    def test_engine_client_remote_error(self):
        mocked = mock.Mock()
        mocked.sync_call.side_effect = rpc_client.RemoteError(
            'InputException',
            'Input is wrong'
        )
        self.engine_client._client = mocked

        self.assertRaises(
            exc.InputException,
            self.engine_client.start_workflow,
            'some_wf',
            {},
            'some_description'
        )

    def test_engine_client_remote_error_arbitrary(self):
        mocked = mock.Mock()
        mocked.sync_call.side_effect = KeyError('wrong key')
        self.engine_client._client = mocked

        exception = self.assertRaises(
            exc.MistralException,
            self.engine_client.start_workflow,
            'some_wf',
            {},
            'some_description'
        )

        self.assertIn('KeyError: wrong key', exception.message)
