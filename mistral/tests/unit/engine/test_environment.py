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
from mistral.executors import default_executor as d_exe
from mistral.executors import remote_executor as r_exe
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
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


def _run_at_target(action_ex_id, action_cls_str, action_cls_attrs,
                   params, safe_rerun, execution_context, target=None,
                   async_=True, timeout=None):
    # We'll just call executor directly for testing purposes.
    executor = d_exe.DefaultExecutor()

    executor.run_action(
        action_ex_id,
        action_cls_str,
        action_cls_attrs,
        params,
        safe_rerun,
        execution_context=execution_context,
        target=target,
        async_=async_,
        timeout=timeout
    )


MOCK_RUN_AT_TARGET = mock.MagicMock(side_effect=_run_at_target)


class EnvironmentTest(base.EngineTestCase):
    def setUp(self):
        super(EnvironmentTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK)

    @mock.patch.object(r_exe.RemoteExecutor, 'run_action', MOCK_RUN_AT_TARGET)
    def _test_subworkflow(self, env):
        wf2_ex = self.engine.start_workflow('my_wb.wf2', env=env)

        # Execution of 'wf2'.
        self.assertIsNotNone(wf2_ex)
        self.assertDictEqual({}, wf2_ex.input)

        self._await(lambda: len(db_api.get_workflow_executions()) == 2, 0.5, 5)

        wf_execs = db_api.get_workflow_executions()

        self.assertEqual(2, len(wf_execs))

        # Execution of 'wf1'.

        wf2_ex = self._assert_single_item(wf_execs, name='my_wb.wf2')
        wf1_ex = self._assert_single_item(wf_execs, name='my_wb.wf1')

        expected_wf1_input = {
            'param1': 'Bonnie',
            'param2': 'Clyde'
        }

        self.assertIsNotNone(wf1_ex.task_execution_id)
        self.assertDictEqual(wf1_ex.input, expected_wf1_input)

        # Wait till workflow 'wf1' is completed.
        self.await_workflow_success(wf1_ex.id)

        with db_api.transaction():
            wf1_ex = db_api.get_workflow_execution(wf1_ex.id)

            self.assertDictEqual(
                {'final_result': "'Bonnie & Clyde'"},
                wf1_ex.output
            )

        # Wait till workflow 'wf2' is completed.
        self.await_workflow_success(wf2_ex.id)

        with db_api.transaction():
            wf2_ex = db_api.get_workflow_execution(wf2_ex.id)

            self.assertDictEqual(
                {'slogan': "'Bonnie & Clyde' is a cool movie!\n"},
                wf2_ex.output
            )

        with db_api.transaction():
            # Check if target is resolved.
            wf1_task_execs = db_api.get_task_executions(
                workflow_execution_id=wf1_ex.id
            )

            self._assert_single_item(wf1_task_execs, name='task1')
            self._assert_single_item(wf1_task_execs, name='task2')

            for t_ex in wf1_task_execs:
                a_ex = t_ex.action_executions[0]

                callback_url = '/v2/action_executions/%s' % a_ex.id

                r_exe.RemoteExecutor.run_action.assert_any_call(
                    a_ex.id,
                    'mistral.actions.std_actions.EchoAction',
                    {},
                    a_ex.input,
                    False,
                    {
                        'task_execution_id': t_ex.id,
                        'callback_url': callback_url,
                        'workflow_execution_id': wf1_ex.id,
                        'workflow_name': wf1_ex.name,
                        'action_execution_id': a_ex.id,
                    },
                    target=TARGET,
                    timeout=None
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

    def test_evaluate_env_parameter(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              publish:
                var1: <% env().var1 %>
                var2: <% env().var2 %>
        """

        wf_service.create_workflows(wf_text)

        env = {
            "var1": "val1",
            "var2": "<% env().var1 %>"
        }

        # Run with 'evaluate_env' set to True.

        wf_ex = self.engine.start_workflow(
            'wf',
            env=env,
            evaluate_env=True
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t = self._assert_single_item(wf_ex.task_executions, name='task1')

            self.assertDictEqual(
                {
                    "var1": "val1",
                    "var2": "val1"
                },
                t.published
            )

        # Run with 'evaluate_env' set to False.

        wf_ex = self.engine.start_workflow(
            'wf',
            env=env,
            evaluate_env=False
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t = self._assert_single_item(wf_ex.task_executions, name='task1')

            self.assertDictEqual(
                {
                    "var1": "val1",
                    "var2": "<% env().var1 %>"
                },
                t.published
            )

    def test_evaluate_env_parameter_subworkflow(self):
        wf_text = """---
        version: '2.0'

        parent_wf:
          tasks:
            task1:
              workflow: sub_wf

        sub_wf:
          output:
            result: <% $.result %>

          tasks:
            task1:
              action: std.noop
              publish:
                result: <% env().dummy %>
        """

        wf_service.create_workflows(wf_text)

        # Run with 'evaluate_env' set to False.

        env = {"dummy": "<% $.ENSURE.MISTRAL.DOESNT.EVALUATE.ENV %>"}

        parent_wf_ex = self.engine.start_workflow(
            'parent_wf',
            env=env,
            evaluate_env=False
        )

        self.await_workflow_success(parent_wf_ex.id)

        with db_api.transaction():
            parent_wf_ex = db_api.get_workflow_execution(parent_wf_ex.id)

            t = self._assert_single_item(
                parent_wf_ex.task_executions,
                name='task1'
            )

            sub_wf_ex = db_api.get_workflow_executions(
                task_execution_id=t.id
            )[0]

            self.assertDictEqual(
                {
                    "result": "<% $.ENSURE.MISTRAL.DOESNT.EVALUATE.ENV %>"
                },
                sub_wf_ex.output
            )

        # Run with 'evaluate_env' set to True.

        env = {"dummy": "<% 1 + 1 %>"}

        parent_wf_ex = self.engine.start_workflow(
            'parent_wf',
            env=env,
            evaluate_env=True
        )

        self.await_workflow_success(parent_wf_ex.id)

        with db_api.transaction():
            parent_wf_ex = db_api.get_workflow_execution(parent_wf_ex.id)

            t = self._assert_single_item(
                parent_wf_ex.task_executions,
                name='task1'
            )

            sub_wf_ex = db_api.get_workflow_executions(
                task_execution_id=t.id
            )[0]

            self.assertDictEqual(
                {
                    "result": 2
                },
                sub_wf_ex.output
            )

    def test_env_not_copied_to_context(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="<% env().param1 %>"
              publish:
                result: <% task().result %>
        """

        wf_service.create_workflows(wf_text)

        env = {
            'param1': 'val1',
            'param2': 'val2',
            'param3': 'val3'
        }

        wf_ex = self.engine.start_workflow('wf', env=env)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        self.assertDictEqual({'result': 'val1'}, t.published)

        self.assertNotIn('__env', wf_ex.context)

    def test_subworkflow_env_no_duplicate(self):
        wf_text = """---
        version: '2.0'

        parent_wf:
          tasks:
            task1:
              workflow: sub_wf

        sub_wf:
          output:
            result: <% $.result %>

          tasks:
            task1:
              action: std.noop
              publish:
                result: <% env().param1 %>
        """

        wf_service.create_workflows(wf_text)

        env = {
            'param1': 'val1',
            'param2': 'val2',
            'param3': 'val3'
        }

        parent_wf_ex = self.engine.start_workflow('parent_wf', env=env)

        self.await_workflow_success(parent_wf_ex.id)

        with db_api.transaction():
            parent_wf_ex = db_api.get_workflow_execution(parent_wf_ex.id)

            t = self._assert_single_item(
                parent_wf_ex.task_executions,
                name='task1'
            )

            sub_wf_ex = db_api.get_workflow_executions(
                task_execution_id=t.id
            )[0]

            self.assertDictEqual(
                {
                    "result": "val1"
                },
                sub_wf_ex.output
            )

        # The environment of the subworkflow must be empty.
        # To evaluate expressions it should be taken from the
        # parent workflow execution.
        self.assertDictEqual({}, sub_wf_ex.params['env'])
        self.assertNotIn('__env', sub_wf_ex.context)
