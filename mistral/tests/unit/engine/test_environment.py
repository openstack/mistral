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

import mock
from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine import default_executor
from mistral.engine.rpc_backend import rpc
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


TARGET = '10.1.15.251'

WORKBOOK = """
---
version: '2.0'

name: my_wb

workflows:
  wf1:
    type: reverse

    input:
      - param1
      - param2

    output:
      final_result: <% $.final_result %>

    tasks:
      task1:
        action: std.echo output=<% $.param1 %>
        target: <% env().var1 %>
        publish:
          result1: <% task(task1).result %>

      task2:
        requires: [task1]
        action: std.echo output="'<% $.result1 %> & <% $.param2 %>'"
        target: <% env().var1 %>
        publish:
          final_result: <% task(task2).result %>

  wf2:
    output:
      slogan: <% $.slogan %>

    tasks:
      task1:
        workflow: wf1
        input:
          param1: <% env().var2 %>
          param2: <% env().var3 %>
          task_name: task2
        publish:
          slogan: >
            <% task(task1).result.final_result %> is a cool <% env().var4 %>!
"""


def _run_at_target(action_ex_id, action_class_str, attributes,
                   action_params, target=None, async=True, safe_rerun=False):
    # We'll just call executor directly for testing purposes.
    executor = default_executor.DefaultExecutor(rpc.get_engine_client())

    executor.run_action(
        action_ex_id,
        action_class_str,
        attributes,
        action_params,
        safe_rerun
    )


MOCK_RUN_AT_TARGET = mock.MagicMock(side_effect=_run_at_target)


class EnvironmentTest(base.EngineTestCase):
    def setUp(self):
        super(EnvironmentTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK)

    @mock.patch.object(rpc.ExecutorClient, 'run_action', MOCK_RUN_AT_TARGET)
    def _test_subworkflow(self, env):
        wf2_ex = self.engine.start_workflow(
            'my_wb.wf2',
            {},
            env=env
        )

        # Execution of 'wf2'.
        self.assertIsNotNone(wf2_ex)
        self.assertDictEqual({}, wf2_ex.input)
        self.assertDictContainsSubset({'env': env}, wf2_ex.params)

        self._await(lambda: len(db_api.get_workflow_executions()) == 2, 0.5, 5)

        wf_execs = db_api.get_workflow_executions()

        self.assertEqual(2, len(wf_execs))

        # Execution of 'wf1'.

        wf2_ex = self._assert_single_item(wf_execs, name='my_wb.wf2')
        wf1_ex = self._assert_single_item(wf_execs, name='my_wb.wf1')

        expected_start_params = {
            'task_name': 'task2',
            'task_execution_id': wf1_ex.task_execution_id,
            'env': env
        }

        expected_wf1_input = {
            'param1': 'Bonnie',
            'param2': 'Clyde'
        }

        self.assertIsNotNone(wf1_ex.task_execution_id)
        self.assertDictContainsSubset(expected_start_params, wf1_ex.params)
        self.assertDictEqual(wf1_ex.input, expected_wf1_input)

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_success(wf1_ex.id)

        wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

        expected_wf1_output = {'final_result': "'Bonnie & Clyde'"}

        self.assertDictEqual(wf1_ex.output, expected_wf1_output)

        # Wait till workflow 'wf2' is completed.
        self.await_workflow_success(wf2_ex.id)

        wf2_ex = db_api.get_workflow_execution(wf2_ex.id)

        expected_wf2_output = {'slogan': "'Bonnie & Clyde' is a cool movie!\n"}

        self.assertDictEqual(wf2_ex.output, expected_wf2_output)

        # Check if target is resolved.
        wf1_task_execs = db_api.get_task_executions(
            workflow_execution_id=wf1_ex.id
        )

        self._assert_single_item(wf1_task_execs, name='task1')
        self._assert_single_item(wf1_task_execs, name='task2')

        for t_ex in wf1_task_execs:
            a_ex = t_ex.action_executions[0]

            rpc.ExecutorClient.run_action.assert_any_call(
                a_ex.id,
                'mistral.actions.std_actions.EchoAction',
                {},
                a_ex.input,
                TARGET,
                safe_rerun=False
            )

    def test_subworkflow_env_task_input(self):
        env = {
            'var1': TARGET,
            'var2': 'Bonnie',
            'var3': 'Clyde',
            'var4': 'movie'
        }

        self._test_subworkflow(env)

    def test_subworkflow_env_recursive(self):
        env = {
            'var1': TARGET,
            'var2': 'Bonnie',
            'var3': '<% env().var5 %>',
            'var4': 'movie',
            'var5': 'Clyde'
        }

        self._test_subworkflow(env)
