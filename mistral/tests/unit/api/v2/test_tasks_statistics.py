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

WF = """
---
version: '2.0'

wf:
  tasks:
    task1:
      action: std.noop
      on-success: task2

    task2:
      action: std.fail
"""

WB = """
---
version: '2.0'

name: wb

workflows:
  parent_wf:
    tasks:
      task1:
        action: std.noop
        on-success: task2

      task2:
        workflow: sub_wf
        on-success: task3

      task3:
        action: std.fail

  sub_wf:
    tasks:
      task1:
        action: std.noop
        on-success: task2

      task2:
        action: std.fail

"""


class TestTasksStatisticsController(base.APITest, engine_base.EngineTestCase):
    def test_simple_sequence_wf(self):
        wf_service.create_workflows(WF)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/tasks_statistics' % wf_ex.id)

        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(1, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(1, stat['SUCCESS'])
        self.assertEqual(2, stat['TOTAL'])

    def test_nested_wf(self):
        wb_service.create_workbook_v2(WB)

        wf_ex = self.engine.start_workflow('wb.parent_wf')

        self.await_workflow_error(wf_ex.id)

        resp = self.app.get(f'/v2/executions/{wf_ex.id}/tasks_statistics')

        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(2, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(2, stat['SUCCESS'])
        self.assertEqual(4, stat['TOTAL'])

    def test_current_only_flag(self):
        wb_service.create_workbook_v2(WB)

        wf_ex = self.engine.start_workflow('wb.parent_wf')

        self.await_workflow_error(wf_ex.id)

        # current_only=true
        resp = self.app.get(
            f'/v2/executions/{wf_ex.id}/tasks_statistics?current_only=true')

        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(1, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(1, stat['SUCCESS'])
        self.assertEqual(2, stat['TOTAL'])

        # current_only=false
        resp = self.app.get(
            f'/v2/executions/{wf_ex.id}/tasks_statistics?current_only=false')

        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(2, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(2, stat['SUCCESS'])
        self.assertEqual(4, stat['TOTAL'])

    def test_child_wf_ex(self):
        wb_service.create_workbook_v2(WB)

        wf_ex = self.engine.start_workflow('wb.parent_wf')
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

            t_ex = self._assert_single_item(
                t_execs,
                name='task2'
            )
            tmp = t_ex.executions
            child_ex = tmp[0]['id']

        # current_only=true
        resp = self.app.get(
            f'/v2/executions/{child_ex}/tasks_statistics?current_only=true')

        self.assertEqual(200, resp.status_int)

        stat = resp.json

        self.assertEqual(1, stat['ERROR'])
        self.assertEqual(0, stat['IDLE'])
        self.assertEqual(0, stat['PAUSED'])
        self.assertEqual(0, stat['RUNNING'])
        self.assertEqual(1, stat['SUCCESS'])
        self.assertEqual(2, stat['TOTAL'])

        # current_only=false
        resp = self.app.get(
            f'/v2/executions/{child_ex}/tasks_statistics?current_only=false',
            expect_errors=True)

        self.assertEqual(400, resp.status_int)
