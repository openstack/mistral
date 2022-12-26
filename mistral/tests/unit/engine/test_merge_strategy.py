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

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from oslo_config import cfg

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class DirectWorkflowEngineTest(base.EngineTestCase):

    def _run_workflow(self, wf_text, wf_input=None,
                      expected_state=states.SUCCESS):
        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', wf_input=wf_input)

        self.await_workflow_state(wf_ex.id, expected_state)

        return db_api.get_workflow_execution(wf_ex.id)

    def test_replace(self):
        self.override_config('merge_strategy', 'replace',
                             group='engine')
        wf_text = """
        version: '2.0'
        wf:
          input:
            - aa:
                bb: wf_ex_input
                cc: wf_ex_input
                zz: wf_ex_input
          output:
            aa: <% $.aa %>
          tasks:
            task1:
              action: std.echo
              # emulate some action result
              input:
                output:
                  cc: task1_res
                  dd: task1_res
              on-success: [task2]
              publish:
                aa:
                  cc: <% task().result["cc"] %>
                  dd: <% task().result["dd"] %>
            task2:
              action: std.echo
              # emulate some action result
              input:
                output:
                  bb: task2_res
              publish:
                aa:
                  bb: <% task().result["bb"] %>
        """

        wf_ex = self._run_workflow(wf_text)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            wf_ex_res = wf_ex.output

            task1 = self._assert_single_item(wf_ex.task_executions,
                                             name='task1')
            task1_publish = task1.published

        expected_wf_ex_res = {
            "aa": {
                "bb": "task2_res"
            }
        }
        self.assertDictEqual(expected_wf_ex_res, wf_ex_res)

        expected_task1_res = {
            "aa": {
                "cc": "task1_res",
                "dd": "task1_res"
            }
        }
        self.assertDictEqual(expected_task1_res, task1_publish)

    def test_merge_input_and_publish(self):
        self.override_config('merge_strategy', 'merge',
                             group='engine')

        wf_text = """
        version: '2.0'

        wf:
          input:
            - aa:
                bb:
                  bb_1: wf_ex_input
                  bb_2: wf_ex_input
                cc: wf_ex_input
          output:
            aa: <% $.aa %>
          tasks:
            task1:
              action: std.echo
              # emulate some action result
              input:
                output:
                  cc: task_res
                  dd: task_res
                  bb_2: task_res
              publish:
                aa:
                  bb:
                    bb_2: <% task().result["bb_2"] %>
                  cc: <% task().result["cc"] %>
                  dd: <% task().result["dd"] %>
        """

        wf_ex = self._run_workflow(wf_text)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            wf_ex_res = wf_ex.output

        expected_wf_ex_res = {
            "aa": {
                "bb": {
                    "bb_1": "wf_ex_input",
                    "bb_2": "task_res"
                },
                "cc": "task_res",
                "dd": "task_res"
            }
        }
        self.assertDictEqual(expected_wf_ex_res, wf_ex_res)

    def test_merge_publish_two_tasks(self):
        self.override_config('merge_strategy', 'merge',
                             group='engine')
        wf_text = """
        version: '2.0'
        wf:
          input:
            - aa:
                bb: wf_ex_input
                cc: wf_ex_input
                zz: wf_ex_input
          output:
            aa: <% $.aa %>
          tasks:
            task1:
              action: std.echo
              # emulate some action result
              input:
                output:
                  cc: task1_res
                  dd: task1_res
              on-success: [task2]
              publish:
                aa:
                  cc: <% task().result["cc"] %>
                  dd: <% task().result["dd"] %>
            task2:
              action: std.echo
              # emulate some action result
              input:
                output:
                  bb: task2_res
              publish:
                aa:
                  bb: <% task().result["bb"] %>
        """

        wf_ex = self._run_workflow(wf_text)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            wf_ex_res = wf_ex.output

        expected_wf_ex_res = {
            "aa": {
                "bb": "task2_res",
                "cc": "task1_res",
                "dd": "task1_res",
                "zz": "wf_ex_input"
            }
        }
        self.assertDictEqual(expected_wf_ex_res, wf_ex_res)

    def test_merge_publish_result_from_join(self):
        self.override_config('merge_strategy', 'merge',
                             group='engine')
        wf_text = """
        version: '2.0'
        wf:
          input:
            - aa:
                aa: wf_ex_input
                bb: wf_ex_input
                cc: wf_ex_input
                zz: wf_ex_input
                dd: wf_ex_input
          output:
            aa: <% $.aa %>
          tasks:
            task0:
              action: std.echo
              # emulate some action result
              input:
                output:
                  res: task0_res
              on-success: [task1, task2]
              publish:
                aa:
                  aa: <% task().result["res"] %>
                  aa_1: <% task().result["res"] %>
            task1:
              action: std.echo
              # emulate some action result
              input:
                output:
                  res: task1_res
              on-success: [task3]
              publish:
                aa:
                  bb: <% task().result["res"] %>
                  bb_1: <% task().result["res"] %>
            task2:
              action: std.echo
              input:
                output:
                  res: task2_res
              on-success: [task3]
              publish:
                aa:
                  cc: <% task().result["res"] %>
                  cc_1: <% task().result["res"] %>
            task3:
              action: std.echo
              join: all
              input:
                output:
                  res: task3_res
              publish:
                aa:
                  zz: <% $.aa.bb_1 + $.aa.cc_1 + $.aa.aa_1 %>
                  zz_1: <% task().result["res"] %>
        """

        wf_ex = self._run_workflow(wf_text)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            wf_ex_res = wf_ex.output

        expected_wf_ex_res = {
            "aa": {
                "aa": "task0_res",
                "aa_1": "task0_res",
                "bb": "task1_res",
                "bb_1": "task1_res",
                "cc": "task2_res",
                "cc_1": "task2_res",
                "zz": "task1_restask2_restask0_res",
                "zz_1": "task3_res",
                "dd": "wf_ex_input"
            }
        }
        self.assertDictEqual(expected_wf_ex_res, wf_ex_res)

    def test_merge_publish_two_parallel_tasks(self):
        self.override_config('merge_strategy', 'merge',
                             group='engine')
        wf_text = """
        version: '2.0'
        wf:
          input:
            - aa:
                bb: wf_ex_input
                cc: wf_ex_input
                dd: wf_ex_input
                ee: wf_ex_input
                zz: wf_ex_input
          output:
            aa: <% $.aa %>
          tasks:
            task_1_1:
              action: std.echo
              # emulate some action result
              input:
                output:
                  res: task_1_1_res
              on-success: [task_2_1]
              publish:
                aa:
                  bb: <% task().result["res"] %>
            task_1_2:
              action: std.echo
              # emulate some action result
              input:
                output:
                  res: task_1_2_res
              on-success: [task_2_1]
              publish:
                aa:
                  cc: <% task().result["res"] %>
            task_2_1:
              action: std.echo
              # emulate some action result
              join: all
              input:
                output:
                  res: task_2_1_res
              on-success: [task_3_1]
              publish:
                aa:
                  dd: <% task().result["res"] %>
            task_3_1:
              action: std.echo
              # emulate some action result
              input:
                output:
                  res: task_3_1_res
              publish:
                aa:
                  ee: <% task().result["res"] %>
        """

        wf_ex = self._run_workflow(wf_text)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            wf_ex_res = wf_ex.output

        expected_wf_ex_res = {
            "aa": {
                "bb": "task_1_1_res",
                "cc": "task_1_2_res",
                "dd": "task_2_1_res",
                "ee": "task_3_1_res",
                "zz": "wf_ex_input"
            }
        }
        self.assertDictEqual(expected_wf_ex_res, wf_ex_res)
