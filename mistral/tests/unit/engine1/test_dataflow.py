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
import testtools

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.openstack.common import log as logging
from mistral.services import workflows as wf_service
from mistral.tests import base as test_base
from mistral.tests.unit.engine1 import base as engine_test_base
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils

LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

SIMPLE_WF = """
---
version: '2.0'

wf:
  type: direct

  tasks:
    task1:
      action: std.echo output="Hi"
      publish:
        hi: $.task1
      on-success:
        - task2

    task2:
      action: std.echo output="Morpheus"
      publish:
        to: $.task2
      on-success:
        - task3

    task3:
      publish:
        result: "{$.hi}, {$.to}! Sincerely, your {$.__env.from}."
"""

PARALLEL_TASKS_WF = """
---
version: 2.0

wf:
  type: direct

  tasks:
    task1:
      action: std.echo output=1
      publish:
        var1: $.task1

    task2:
      action: std.echo output=2
      publish:
        var2: $.task2
"""

VAR_OVERWRITE_WF = """
---
version: '2.0'

wf:
  type: direct

  tasks:
    task1:
      action: std.echo output="Hi"
      publish:
        greeting: $.task1
      on-success:
        - task2

    task2:
      action: std.echo output="Yo"
      publish:
        greeting: $.task2
      on-success:
        - task3

    task3:
      action: std.echo output="Morpheus"
      publish:
        to: $.task3
      on-success:
        - task4

    task4:
      publish:
        result: "{$.greeting}, {$.to}! Sincerely, your {$.__env.from}."
"""


class DataFlowEngineTest(engine_test_base.EngineTestCase):
    def test_trivial_dataflow(self):
        wf_service.create_workflows(SIMPLE_WF)

        # Start workflow.
        exec_db = self.engine.start_workflow(
            'wf',
            {},
            env={'from': 'Neo'}
        )

        self._await(lambda: self.is_execution_success(exec_db.id))

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)

        tasks = exec_db.tasks

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.SUCCESS, task3.state)
        self.assertDictEqual({'hi': 'Hi'}, task1.output)
        self.assertDictEqual({'to': 'Morpheus'}, task2.output)
        self.assertDictEqual(
            {'result': 'Hi, Morpheus! Sincerely, your Neo.'},
            task3.output
        )

    # TODO(rakhmerov): https://bugs.launchpad.net/mistral/+bug/1414821.
    @testtools.skip('Make it work.')
    def test_parallel_tasks(self):
        wf_service.create_workflows(PARALLEL_TASKS_WF)

        # Start workflow.
        exec_db = self.engine.start_workflow('wf', {})

        self._await(lambda: self.is_execution_success(exec_db.id))

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)

        tasks = exec_db.tasks

        self.assertEqual(2, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)

        self.assertDictEqual({'var1': 1}, task1.output)
        self.assertDictEqual({'var2': 2}, task2.output)

        self.assertEqual(1, exec_db.output['var1'])
        self.assertEqual(2, exec_db.output['var2'])

    def test_sequential_tasks_publishing_same_var(self):
        wf_service.create_workflows(VAR_OVERWRITE_WF)

        # Start workflow.
        exec_db = self.engine.start_workflow(
            'wf',
            {},
            env={'from': 'Neo'}
        )

        self._await(lambda: self.is_execution_success(exec_db.id))

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)

        tasks = exec_db.tasks

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')
        task4 = self._assert_single_item(tasks, name='task4')

        self.assertEqual(states.SUCCESS, task4.state)
        self.assertDictEqual({'greeting': 'Hi'}, task1.output)
        self.assertDictEqual({'greeting': 'Yo'}, task2.output)
        self.assertDictEqual({'to': 'Morpheus'}, task3.output)
        self.assertDictEqual(
            {'result': 'Yo, Morpheus! Sincerely, your Neo.'},
            task4.output
        )


class DataFlowTest(test_base.BaseTest):
    def test_evaluate_task_output_simple(self):
        """Test simplest green-path scenario:
        action status is SUCCESS, action output is string
        published variables are static (no expression),
        environment __env is absent.

        Expected to get publish variables AS IS.
        """
        publish_dict = {'foo': 'bar'}
        action_output = 'string data'
        task_db = models.Task(name='task1')
        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish_dict)
        raw_result = utils.TaskResult(data=action_output, error=None)

        res = data_flow.evaluate_task_output(task_db, task_spec, raw_result)

        self.assertEqual(res['foo'], 'bar')

    def test_evaluate_task_output(self):
        """Test green-path scenario with evaluations
        action status is SUCCESS, action output is dict
        published variables with expression,
        environment __env is present.

        Expected to get resolved publish variables.
        """
        in_context = {
            'var': 'val',
            '__env': {'ekey': 'edata'}
        }

        action_output = {'akey': 'adata'}

        publish = {
            'v': '{$.var}',
            'e': '$.__env.ekey',
            'a': '{$.task1.akey}'
        }

        task_db = models.Task(name='task1')
        task_db.in_context = in_context

        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish)

        raw_result = utils.TaskResult(data=action_output, error=None)

        res = data_flow.evaluate_task_output(task_db, task_spec, raw_result)

        self.assertEqual(3, len(res))

        # Resolved from inbound context.
        self.assertEqual(res['v'], 'val')

        # Resolved from environment.
        self.assertEqual(res['e'], 'edata')

        # Resolved from action output.
        self.assertEqual(res['a'], 'adata')

    def test_evaluate_task_output_with_error(self):
        """Test handling ERROR in action
        action status is ERROR, action output is error string
        published variables should not evaluate,

        Expected to get action error.
        """
        publish = {'foo': '$.akey'}
        action_output = 'error data'

        task_db = models.Task(name='task1')

        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish)

        raw_result = utils.TaskResult(data=None, error=action_output)

        res = data_flow.evaluate_task_output(task_db, task_spec, raw_result)

        self.assertDictEqual(
            res,
            {
                'error': action_output,
                'task': {'task1': action_output}
            }
        )
