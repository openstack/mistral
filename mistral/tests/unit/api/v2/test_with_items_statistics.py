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
from mistral.tests.unit.api import base
from mistral.tests.unit.engine import base as engine_base
from mistral.workflow import states


WF = """
---
version: '2.0'
with_items_wf_action:
  tasks:
    t1:
      with-items: v in <% list(range(0, 50)) %>
      action: std.noop

"""


WF_FAIL = """
---
version: '2.0'
with_items_wf_fail:
  tasks:
    t1:
      with-items: v in <% list(range(0, 50)) %>
      action: std.fail

"""


WB_WITH_ITEMS = """
---
version: '2.0'

name: wb

workflows:
  with_items_wf:
    tasks:
      t1:
        with-items: v in <% list(range(0, 50)) %>
        workflow: subworkflow_from_with_items

  subworkflow_from_with_items:
    tasks:
      t1:
        action: std.noop
"""


class TestWithItemsStatisticsController(base.APITest,
                                        engine_base.EngineTestCase):
    def test_action(self):
        wf_service.create_workflows(WF)

        wf_ex = self.engine.start_workflow('with_items_wf_action')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='t1',
                state=states.SUCCESS
            )

        resp = self.app.get(f'/v2/tasks/{t_ex.id}/with_items_statistics')
        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(0, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(50, stat['SUCCESS'])
        self.assertEqual(50, stat['TOTAL'])

    def test_fail_action(self):
        wf_service.create_workflows(WF_FAIL)

        wf_ex = self.engine.start_workflow('with_items_wf_fail')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='t1',
                state=states.ERROR
            )

        resp = self.app.get(f'/v2/tasks/{t_ex.id}/with_items_statistics')
        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(50, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(0, stat['SUCCESS'])
        self.assertEqual(50, stat['TOTAL'])

    def test_workflow(self):
        wb_service.create_workbook_v2(WB_WITH_ITEMS)

        wf_ex = self.engine.start_workflow('wb.with_items_wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='t1',
                state=states.SUCCESS
            )

        resp = self.app.get(f'/v2/tasks/{t_ex.id}/with_items_statistics')
        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(0, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(50, stat['SUCCESS'])
        self.assertEqual(50, stat['TOTAL'])
