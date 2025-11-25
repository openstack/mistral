# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


class WorkflowReadOnlyTest(base.EngineTestCase):
    def test_read_only_sets_correctly_on_successed_workflow(self):
        workflow = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.noop
                - task2
            task2:
              action: std.noop
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            self.assertTrue(wf_ex.params['read_only'])

        self.assertEqual(states.SUCCESS, wf_ex.state)

    def test_recursive_set_read_only(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf1:
              type: direct
              tasks:
                wf1t1:
                  workflow: wf2
            wf2:
              type: direct
              tasks:
                wf2t1:
                  workflow: wf3
            wf3:
              type: direct
              tasks:
                wf3t1:
                  action: std.fail
        """

        wb_service.create_workbook_v2(workbook)

        self.engine.start_workflow('wb.wf1')

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            wf1_ex = self._assert_single_item(wf_execs, name='wb.wf1')

        self.await_workflow_error(wf1_ex.id)

        self.engine.update_wf_ex_to_read_only(wf1_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()

            wf1_ex = self._assert_single_item(wf_execs, name='wb.wf1')
            wf2_ex = self._assert_single_item(wf_execs, name='wb.wf2')
            wf3_ex = self._assert_single_item(wf_execs, name='wb.wf3')

            self.assertEqual(states.ERROR, wf1_ex.state)
            self.assertTrue(wf1_ex.params['read_only'])
            self.assertEqual(states.ERROR, wf2_ex.state)
            self.assertTrue(wf2_ex.params['read_only'])
            self.assertEqual(states.ERROR, wf3_ex.state)
            self.assertTrue(wf3_ex.params['read_only'])
