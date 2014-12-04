# Copyright 2014 - Mirantis, Inc.
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
        action: std.echo output="{$.param1}"
        publish:
            result: $

      task2:
        action: std.echo output="{$.param2}"
        requires: [task1]

"""

# TODO(rakhmerov): Add more advanced tests including various capabilities.


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
        exec_db = self.engine.start_workflow(
            'wb.wf1',
            wf_input,
            task_name='task2'
        )

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.RUNNING, exec_db.state)
        self._assert_dict_contains_subset(wf_input, exec_db.context)
        self.assertIn('__execution', exec_db.context)

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(1, len(exec_db.tasks))

        task_db = exec_db.tasks[0]

        self.assertEqual('wb.wf1', task_db.wf_name)
        self.assertEqual('task1', task_db.name)
        self.assertEqual(states.RUNNING, task_db.state)
        self.assertIsNotNone(task_db.spec)
        self.assertIsNone(task_db.runtime_context)

        # Data Flow properties.
        self._assert_dict_contains_subset(wf_input, task_db.in_context)
        self.assertIn('__execution', task_db.in_context)
        self.assertDictEqual({'output': 'Hey'}, task_db.input)

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
        exec_db = self.engine.start_workflow(
            'wb.wf1',
            wf_input,
            task_name='task2'
        )

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.RUNNING, exec_db.state)

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(1, len(exec_db.tasks))

        task_db = exec_db.tasks[0]

        self.assertEqual('task1', task_db.name)
        self.assertEqual(states.RUNNING, task_db.state)
        self.assertIsNotNone(task_db.spec)
        self.assertIsNone(task_db.runtime_context)
        self._assert_dict_contains_subset(wf_input, task_db.in_context)
        self.assertIn('__execution', task_db.in_context)
        self.assertDictEqual({'output': 'Hey'}, task_db.input)

        # Finish 'task1'.
        task1_db = self.engine.on_task_result(
            exec_db.tasks[0].id,
            wf_utils.TaskResult(data='Hey')
        )

        self.assertIsInstance(task1_db, models.Task)
        self.assertEqual('task1', task1_db.name)
        self.assertEqual(states.SUCCESS, task1_db.state)

        # Data Flow properties.
        self._assert_dict_contains_subset(wf_input, task1_db.in_context)
        self.assertIn('__execution', task_db.in_context)
        self.assertDictEqual({'output': 'Hey'}, task1_db.input)
        self.assertDictEqual(
            {
                'result': 'Hey',
                'task': {'task1': {'result': 'Hey'}}
            },
            task1_db.output
        )

        exec_db = db_api.get_execution(exec_db.id)

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.RUNNING, exec_db.state)

        self.assertEqual(2, len(exec_db.tasks))

        task2_db = self._assert_single_item(exec_db.tasks, name='task2')

        self.assertEqual(states.RUNNING, task2_db.state)

        # Finish 'task2'.
        task2_db = self.engine.on_task_result(
            task2_db.id,
            wf_utils.TaskResult(data='Hi')
        )

        exec_db = db_api.get_execution(exec_db.id)

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.SUCCESS, exec_db.state)

        self.assertIsInstance(task2_db, models.Task)
        self.assertEqual('task2', task2_db.name)
        self.assertEqual(states.SUCCESS, task2_db.state)

        in_context = copy.deepcopy(wf_input)
        in_context.update(task1_db.output)

        self._assert_dict_contains_subset(in_context, task2_db.in_context)
        self.assertIn('__execution', task_db.in_context)
        self.assertDictEqual({'output': 'Hi'}, task2_db.input)
        self.assertDictEqual({'task': {'task2': None}}, task2_db.output)

        self.assertEqual(2, len(exec_db.tasks))

        self._assert_single_item(exec_db.tasks, name='task1')
        self._assert_single_item(exec_db.tasks, name='task2')

    def test_stop_workflow(self):
        # TODO(akhmerov): Implement.
        pass

    def test_resume_workflow(self):
        # TODO(akhmerov): Implement.
        pass
