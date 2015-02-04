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
from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine1 import rpc
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base


LOG = logging.getLogger(__name__)

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
      final_result: $.final_result

    tasks:
      task1:
        action: std.echo output='{$.param1}'
        target: $.__env.var1
        publish:
          result1: $.task1

      task2:
        requires: [task1]
        action: std.echo output="'{$.result1} & {$.param2}'"
        target: $.__env.var1
        publish:
          final_result: $.task2

  wf2:
    type: direct

    output:
      slogan: $.slogan

    tasks:
      task1:
        workflow: wf1
        input:
          param1: $.__env.var2
          param2: $.__env.var3
          task_name: task2
        publish:
          slogan: "{$.task1.final_result} is a cool {$.__env.var4}!"
"""


def _run_at_target(task_id, action_class_str, attributes,
                   action_params, target=None):
    kwargs = {
        'task_id': task_id,
        'action_class_str': action_class_str,
        'attributes': attributes,
        'params': action_params
    }

    rpc_client = rpc.get_executor_client()
    rpc_client._cast_run_action(rpc_client.topic, **kwargs)


MOCK_RUN_AT_TARGET = mock.MagicMock(side_effect=_run_at_target)


class SubworkflowsTest(base.EngineTestCase):
    def setUp(self):
        super(SubworkflowsTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK)

    @mock.patch.object(rpc.ExecutorClient, 'run_action', MOCK_RUN_AT_TARGET)
    def _test_subworkflow(self, env):
        exec1_db = self.engine.start_workflow(
            'my_wb.wf2',
            None,
            env=env
        )

        # Execution 1.
        self.assertIsNotNone(exec1_db)
        self.assertDictEqual({}, exec1_db.input)
        self.assertDictEqual({'env': env}, exec1_db.start_params)

        db_execs = db_api.get_executions()

        self.assertEqual(2, len(db_execs))

        # Execution 2.
        if db_execs[0].id != exec1_db.id:
            exec2_db = db_execs[0]
        else:
            exec2_db = db_execs[1]

        expected_start_params = {
            'task_name': 'task2',
            'parent_task_id': exec2_db.parent_task_id,
            'env': env
        }

        expected_wf1_input = {
            'param1': 'Bonnie',
            'param2': 'Clyde'
        }

        self.assertIsNotNone(exec2_db.parent_task_id)
        self.assertDictEqual(exec2_db.start_params, expected_start_params)
        self.assertDictEqual(exec2_db.input, expected_wf1_input)

        # Wait till workflow 'wf1' is completed.
        self._await(lambda: self.is_execution_success(exec2_db.id))

        exec2_db = db_api.get_execution(exec2_db.id)

        expected_wf1_output = {'final_result': "'Bonnie & Clyde'"}

        self.assertDictEqual(exec2_db.output, expected_wf1_output)

        # Wait till workflow 'wf2' is completed.
        self._await(lambda: self.is_execution_success(exec1_db.id))

        exec1_db = db_api.get_execution(exec1_db.id)

        expected_wf2_output = {'slogan': "'Bonnie & Clyde' is a cool movie!"}

        self.assertDictEqual(exec1_db.output, expected_wf2_output)

        # Check if target is resolved.
        tasks_exec2 = db_api.get_tasks(execution_id=exec2_db.id)

        self._assert_single_item(tasks_exec2, name='task1')
        self._assert_single_item(tasks_exec2, name='task2')

        for task in tasks_exec2:
            rpc.ExecutorClient.run_action.assert_any_call(
                task.id,
                'mistral.actions.std_actions.EchoAction',
                {},
                task.input,
                TARGET
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
            'var3': '{$.__env.var5}',
            'var4': 'movie',
            'var5': 'Clyde'
        }

        self._test_subworkflow(env)
