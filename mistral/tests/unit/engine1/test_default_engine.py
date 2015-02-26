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

import copy
import datetime
import uuid

import mock
from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.engine1 import default_engine as d_eng
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests import base
from mistral.workflow import states
from mistral.workflow import utils as wf_utils

LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
version: '2.0'

name: wb

workflows:
  wf1:
    type: reverse
    input:
      - param1
      - param2

    tasks:
      task1:
        action: std.echo output=<% $.param1 %>
        publish:
            result: <% $.task1 %>

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
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())


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
            'wb.wf1',
            wf_input,
            task_name='task2'
        )

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex.state)
        self._assert_dict_contains_subset(wf_input, wf_ex.context)
        self.assertIn('__execution', wf_ex.context)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))

        task_ex = wf_ex.task_executions[0]

        self.assertEqual('wb.wf1', task_ex.workflow_name)
        self.assertEqual('task1', task_ex.name)
        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertIsNotNone(task_ex.spec)
        self.assertDictEqual({}, task_ex.runtime_context)

        # Data Flow properties.
        self._assert_dict_contains_subset(wf_input, task_ex.in_context)
        self.assertIn('__execution', task_ex.in_context)
        self.assertDictEqual({'output': 'Hey'}, task_ex.input)

    def test_start_workflow_with_adhoc_env(self):
        wf_input = {
            'param1': '<% $.__env.key1 %>',
            'param2': '<% $.__env.key2 %>'
        }
        env = ENVIRONMENT['variables']

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input,
            env=env,
            task_name='task2')

        self.assertIsNotNone(wf_ex)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertDictEqual(wf_ex.start_params.get('env', {}), env)

    @mock.patch.object(db_api, "get_environment", MOCK_ENVIRONMENT)
    def test_start_workflow_with_saved_env(self):
        wf_input = {
            'param1': '<% $.__env.key1 %>',
            'param2': '<% $.__env.key2 %>'
        }
        env = ENVIRONMENT['variables']

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input,
            env='test',
            task_name='task2')

        self.assertIsNotNone(wf_ex)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertDictEqual(wf_ex.start_params.get('env', {}), env)

    @mock.patch.object(db_api, "get_environment", MOCK_NOT_FOUND)
    def test_start_workflow_env_not_found(self):
        self.assertRaises(exc.NotFoundException,
                          self.engine.start_workflow,
                          'wb.wf1',
                          {'param1': '<% $.__env.key1 %>'},
                          env='foo',
                          task_name='task2')

    def test_start_workflow_with_env_type_error(self):
        self.assertRaises(ValueError,
                          self.engine.start_workflow,
                          'wb.wf1',
                          {'param1': '<% $.__env.key1 %>'},
                          env=True,
                          task_name='task2')

    def test_start_workflow_missing_parameters(self):
        self.assertRaises(
            exc.WorkflowInputException,
            self.engine.start_workflow,
            'wb.wf1',
            None,
            task_name='task2'
        )

    def test_start_workflow_unexpected_parameters(self):
        self.assertRaises(
            exc.WorkflowInputException,
            self.engine.start_workflow,
            'wb.wf1',
            {'param1': 'Hey', 'param2': 'Hi', 'unexpected_param': 'val'},
            task_name='task2'
        )

    def test_on_task_result(self):
        wf_input = {'param1': 'Hey', 'param2': 'Hi'}

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1',
            wf_input,
            task_name='task2'
        )

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex.state)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))

        task_ex = wf_ex.task_executions[0]

        self.assertEqual('task1', task_ex.name)
        self.assertEqual(states.RUNNING, task_ex.state)
        self.assertIsNotNone(task_ex.spec)
        self.assertDictEqual({}, task_ex.runtime_context)
        self._assert_dict_contains_subset(wf_input, task_ex.in_context)
        self.assertIn('__execution', task_ex.in_context)
        self.assertDictEqual({'output': 'Hey'}, task_ex.input)

        # Finish 'task1'.
        task1_db = self.engine.on_task_result(
            wf_ex.task_executions[0].id,
            wf_utils.TaskResult(data='Hey')
        )

        self.assertIsInstance(task1_db, models.TaskExecution)
        self.assertEqual('task1', task1_db.name)
        self.assertEqual(states.SUCCESS, task1_db.state)

        # Data Flow properties.
        self._assert_dict_contains_subset(wf_input, task1_db.in_context)
        self.assertIn('__execution', task_ex.in_context)
        self.assertDictEqual({'output': 'Hey'}, task1_db.input)
        self.assertDictEqual({'result': 'Hey'}, task1_db.result)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex.state)

        self.assertEqual(2, len(wf_ex.task_executions))

        task2_db = self._assert_single_item(
            wf_ex.task_executions,
            name='task2'
        )

        self.assertEqual(states.RUNNING, task2_db.state)

        # Finish 'task2'.
        task2_db = self.engine.on_task_result(
            task2_db.id,
            wf_utils.TaskResult(data='Hi')
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.SUCCESS, wf_ex.state)

        self.assertIsInstance(task2_db, models.TaskExecution)
        self.assertEqual('task2', task2_db.name)
        self.assertEqual(states.SUCCESS, task2_db.state)

        in_context = copy.deepcopy(wf_input)
        in_context.update(task1_db.result)

        self._assert_dict_contains_subset(in_context, task2_db.in_context)
        self.assertIn('__execution', task_ex.in_context)
        self.assertDictEqual({'output': 'Hi'}, task2_db.input)
        self.assertDictEqual({}, task2_db.result)

        self.assertEqual(2, len(wf_ex.task_executions))

        self._assert_single_item(wf_ex.task_executions, name='task1')
        self._assert_single_item(wf_ex.task_executions, name='task2')

    def test_stop_workflow_fail(self):
        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1', {'param1': 'Hey', 'param2': 'Hi'}, task_name="task2")
        # Re-read execution to access related tasks.
        wf_ex = db_api.get_execution(wf_ex.id)

        self.engine.stop_workflow(wf_ex.id, 'ERROR', "Stop this!")

        # Re-read from DB again
        wf_ex = db_api.get_execution(wf_ex.id)

        self.assertEqual('ERROR', wf_ex.state)
        self.assertEqual("Stop this!", wf_ex.state_info)

    def test_stop_workflow_succeed(self):
        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wb.wf1', {'param1': 'Hey', 'param2': 'Hi'}, task_name="task2")
        # Re-read execution to access related tasks.
        wf_ex = db_api.get_execution(wf_ex.id)

        self.engine.stop_workflow(wf_ex.id, 'SUCCESS', "Like this, done")

        # Re-read from DB again
        wf_ex = db_api.get_execution(wf_ex.id)

        self.assertEqual('SUCCESS', wf_ex.state)
        self.assertEqual("Like this, done", wf_ex.state_info)

    def test_stop_workflow_bad_status(self):
        wf_ex = self.engine.start_workflow(
            'wb.wf1', {'param1': 'Hey', 'param2': 'Hi'}, task_name="task2")
        # Re-read execution to access related tasks.
        wf_ex = db_api.get_execution(wf_ex.id)

        self.assertRaises(
            exc.WorkflowException,
            self.engine.stop_workflow,
            wf_ex.id,
            'PAUSE'
        )

    def test_resume_workflow(self):
        # TODO(akhmerov): Implement.
        pass
