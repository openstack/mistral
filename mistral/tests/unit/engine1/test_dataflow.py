# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

LINEAR_WF = """
---
version: '2.0'

wf:
  type: direct

  tasks:
    task1:
      action: std.echo output="Hi"
      publish:
        hi: <% $.task1 %>
      on-success:
        - task2

    task2:
      action: std.echo output="Morpheus"
      publish:
        to: <% $.task2 %>
      on-success:
        - task3

    task3:
      publish:
        result: "<% $.hi %>, <% $.to %>! Sincerely, your <% $.__env.from %>."
"""

LINEAR_WITH_BRANCHES_WF = """
---
version: '2.0'

wf:
  type: direct

  tasks:
    task1:
      action: std.echo output="Hi"
      publish:
        hi: <% $.task1 %>
        progress: "completed task1"
      on-success:
        - notify
        - task2

    task2:
      action: std.echo output="Morpheus"
      publish:
        to: <% $.task2 %>
        progress: "completed task2"
      on-success:
        - notify
        - task3

    task3:
      publish:
        result: "<% $.hi %>, <% $.to %>! Sincerely, your <% $.__env.from %>."
        progress: "completed task3"
      on-success:
        - notify

    notify:
      action: std.echo output=<% $.progress %>
      publish:
        progress: <% $.notify %>
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
        var1: <% $.task1 %>

    task2:
      action: std.echo output=2
      publish:
        var2: <% $.task2 %>
"""

PARALLEL_TASKS_COMPLEX_WF = """
---
version: 2.0

wf:
  type: direct

  tasks:
    task1:
      action: std.noop
      publish:
        var1: 1
      on-complete:
        - task12

    task12:
      action: std.noop
      publish:
        var12: 12
      on-complete:
        - task13
        - task14

    task13:
      action: std.fail
      description: |
        Since this task fails we expect that 'var13' won't go into context.
        Only 'var14'.
      publish:
        var13: 13
      on-error:
        - noop

    task14:
      publish:
        var14: 14

    task2:
      publish:
        var2: 2
      on-complete:
        - task21

    task21:
      publish:
        var21: 21
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
        greeting: <% $.task1 %>
      on-success:
        - task2

    task2:
      action: std.echo output="Yo"
      publish:
        greeting: <% $.task2 %>
      on-success:
        - task3

    task3:
      action: std.echo output="Morpheus"
      publish:
        to: <% $.task3 %>
      on-success:
        - task4

    task4:
      publish:
        result: "<% $.greeting %>, <% $.to %>! Your <% $.__env.from %>."
"""


class DataFlowEngineTest(engine_test_base.EngineTestCase):
    def test_linear_dataflow(self):
        wf_service.create_workflows(LINEAR_WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            {},
            env={'from': 'Neo'}
        )

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.SUCCESS, task3.state)
        self.assertDictEqual({'hi': 'Hi'}, task1.result)
        self.assertDictEqual({'to': 'Morpheus'}, task2.result)
        self.assertDictEqual(
            {'result': 'Hi, Morpheus! Sincerely, your Neo.'},
            task3.result
        )

    def test_linear_with_branches_dataflow(self):
        wf_service.create_workflows(LINEAR_WITH_BRANCHES_WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            {},
            env={'from': 'Neo'}
        )

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')
        notifies = self._assert_multiple_items(tasks, 3, name='notify')
        notify_results = [notify.result['progress'] for notify in notifies]

        self.assertEqual(states.SUCCESS, task3.state)

        results = [
            {'hi': 'Hi', 'progress': 'completed task1'},
            {'to': 'Morpheus', 'progress': 'completed task2'},
            {'result': 'Hi, Morpheus! Sincerely, your Neo.',
             'progress': 'completed task3'}
        ]

        self.assertDictEqual(results[0], task1.result)
        self.assertDictEqual(results[1], task2.result)
        self.assertDictEqual(results[2], task3.result)
        self.assertIn(results[0]['progress'], notify_results)
        self.assertIn(results[1]['progress'], notify_results)
        self.assertIn(results[2]['progress'], notify_results)

    def test_parallel_tasks(self):
        wf_service.create_workflows(PARALLEL_TASKS_WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        tasks = wf_ex.task_executions

        self.assertEqual(2, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)

        self.assertDictEqual({'var1': 1}, task1.result)
        self.assertDictEqual({'var2': 2}, task2.result)

        self.assertEqual(1, wf_ex.output['var1'])
        self.assertEqual(2, wf_ex.output['var2'])

    def test_parallel_tasks_complex(self):
        wf_service.create_workflows(PARALLEL_TASKS_COMPLEX_WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        tasks = wf_ex.task_executions

        self.assertEqual(6, len(tasks))

        task1 = self._assert_single_item(tasks, name='task1')
        task12 = self._assert_single_item(tasks, name='task12')
        task13 = self._assert_single_item(tasks, name='task13')
        task14 = self._assert_single_item(tasks, name='task14')
        task2 = self._assert_single_item(tasks, name='task2')
        task21 = self._assert_single_item(tasks, name='task21')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task12.state)
        self.assertEqual(states.ERROR, task13.state)
        self.assertEqual(states.SUCCESS, task14.state)
        self.assertEqual(states.SUCCESS, task2.state)
        self.assertEqual(states.SUCCESS, task21.state)

        self.assertDictEqual({'var1': 1}, task1.result)
        self.assertDictEqual({'var12': 12}, task12.result)
        self.assertDictEqual({'var14': 14}, task14.result)
        self.assertDictEqual({'var2': 2}, task2.result)
        self.assertDictEqual({'var21': 21}, task21.result)

        self.assertEqual(1, wf_ex.output['var1'])
        self.assertEqual(12, wf_ex.output['var12'])
        self.assertFalse('var13' in wf_ex.output)
        self.assertEqual(14, wf_ex.output['var14'])
        self.assertEqual(2, wf_ex.output['var2'])
        self.assertEqual(21, wf_ex.output['var21'])

    def test_sequential_tasks_publishing_same_var(self):
        wf_service.create_workflows(VAR_OVERWRITE_WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            {},
            env={'from': 'Neo'}
        )

        self._await(lambda: self.is_execution_success(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')
        task4 = self._assert_single_item(tasks, name='task4')

        self.assertEqual(states.SUCCESS, task4.state)
        self.assertDictEqual({'greeting': 'Hi'}, task1.result)
        self.assertDictEqual({'greeting': 'Yo'}, task2.result)
        self.assertDictEqual({'to': 'Morpheus'}, task3.result)
        self.assertDictEqual(
            {'result': 'Yo, Morpheus! Your Neo.'},
            task4.result
        )


class DataFlowTest(test_base.BaseTest):
    def test_evaluate_task_result_simple(self):
        """Test simplest green-path scenario:
        action status is SUCCESS, action output is string
        published variables are static (no expression),
        environment __env is absent.

        Expected to get publish variables AS IS.
        """
        publish_dict = {'foo': 'bar'}
        action_output = 'string data'

        task_ex = models.TaskExecution(name='task1')

        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish_dict)

        res = data_flow.evaluate_task_result(
            task_ex,
            task_spec,
            utils.TaskResult(data=action_output, error=None)
        )

        self.assertEqual(res['foo'], 'bar')

    def test_evaluate_task_result(self):
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
            'v': '<% $.var %>',
            'e': '<% $.__env.ekey %>',
            'a': '<% $.task1.akey %>'
        }

        task_ex = models.TaskExecution(name='task1')
        task_ex.in_context = in_context

        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish)

        res = data_flow.evaluate_task_result(
            task_ex,
            task_spec,
            utils.TaskResult(data=action_output, error=None)
        )

        self.assertEqual(3, len(res))

        # Resolved from inbound context.
        self.assertEqual(res['v'], 'val')

        # Resolved from environment.
        self.assertEqual(res['e'], 'edata')

        # Resolved from action output.
        self.assertEqual(res['a'], 'adata')

    def test_evaluate_task_result_with_error(self):
        """Test handling ERROR in action
        action status is ERROR, action output is error string
        published variables should not evaluate,

        Expected to get action error.
        """
        publish = {'foo': '<% $.akey %>'}
        action_output = 'error data'

        task_ex = models.TaskExecution(name='task1')

        task_spec = mock.MagicMock()
        task_spec.get_publish = mock.MagicMock(return_value=publish)

        res = data_flow.evaluate_task_result(
            task_ex,
            task_spec,
            utils.TaskResult(data=None, error=action_output)
        )

        self.assertDictEqual(
            res,
            {
                'error': action_output,
                'task': {'task1': action_output}
            }
        )
