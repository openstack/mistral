# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import mock
from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests import base as testbase
from mistral.tests.unit.engine1 import base as testengine1
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils

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
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi,"
        publish:
          hi: $
        on-success:
          - task2

      task2:
        action: std.echo output="Morpheus"
        publish:
          username: $
        on-success:
          - task3

      task3:
        action: std.echo output="{$.hi} {$.username}.Nebuchadnezzar!"
        publish:
          result: $
"""


class DataFlowEngineTest(testengine1.EngineTestCase):
    def setUp(self):
        super(DataFlowEngineTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK)

    def test_trivial_dataflow(self):
        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        self._await(
            lambda: self.is_execution_success(exec_db.id),
        )

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)

        tasks = exec_db.tasks

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.SUCCESS, task3.state)

        self.assertDictEqual(
            {
                'task': {
                    'task1': {'hi': 'Hi,'},
                },
                'hi': 'Hi,',
            },
            task1.output
        )

        self.assertDictEqual(
            {
                'task': {
                    'task2': {'username': 'Morpheus'},
                },
                'username': 'Morpheus',
            },
            task2.output
        )

        self.assertDictEqual(
            {
                'task': {
                    'task3': {'result': 'Hi, Morpheus.Nebuchadnezzar!'},
                },
                'result': 'Hi, Morpheus.Nebuchadnezzar!',
            },
            task3.output
        )


class DataFlowTest(testbase.BaseTest):
    def test_evaluate_task_output_simple(self):
        """Test simplest green-path scenario:
        action status is SUCCESS, action output is string
        published variables are static (no expression),
        environment __env is absent.

        Expected to get publish variables AS IS.
        """
        publish_dict = {'foo': 'bar'}
        action_output = "string data"
        task_db = models.Task(name="task1")
        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish_dict)
        raw_result = utils.TaskResult(data=action_output, error=None)

        res = data_flow.evaluate_task_output(task_db, task_spec, raw_result)

        self.assertEqual(res['foo'], "bar")
        self.assertEqual(res['task']['task1'], publish_dict)

    def test_evaluate_task_output(self):
        """Test green-path scenario with evaluations
        action status is SUCCESS, action output is dict
        published variables with expression,
        environment __env is present.

        Expected to get resolved publish variables.
        """
        publish_dict = {'a': '{$.akey}', 'e': "$.__env.ekey"}
        action_output = {'akey': "adata"}
        env = {'ekey': "edata"}
        task_db = models.Task(name="task1")
        task_db.in_context = {'__env': env}
        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish_dict)
        raw_result = utils.TaskResult(data=action_output, error=None)

        res = data_flow.evaluate_task_output(task_db, task_spec, raw_result)
        self.assertEqual(res['a'], "adata")
        self.assertEqual(res['e'], "edata")
        self.assertEqual(res['task']['task1'], {'a': "adata", 'e': 'edata'})

    def test_evaluate_task_output_with_error(self):
        """Test handling ERROR in action
        action status is ERROR, action output is error string
        published variables should not evaluate,

        Expected to get action error.
        """
        publish_dict = {'foo': '$.akey'}
        action_output = "error data"
        task_db = models.Task(name="task1")
        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish_dict)
        raw_result = utils.TaskResult(data=None, error=action_output)

        res = data_flow.evaluate_task_output(task_db, task_spec, raw_result)

        self.assertDictEqual(
            res, {'error': action_output, 'task': {'task1': action_output}})
