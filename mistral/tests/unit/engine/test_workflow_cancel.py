# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


class WorkflowCancelTest(base.EngineTestCase):
    def test_cancel_workflow(self):
        workflow = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2

            task2:
              action: std.echo output="foo"
              wait-before: 3
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf', {})

        self.engine.stop_workflow(
            wf_ex.id,
            states.CANCELLED,
            "Cancelled by user."
        )

        self.await_workflow_cancelled(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.await_task_success(task_1_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled by user.", wf_ex.state_info)
        self.assertEqual(1, len(wf_ex.task_executions))
        self.assertEqual(states.SUCCESS, task_1_ex.state)

    def test_cancel_paused_workflow(self):
        workflow = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2

            task2:
              action: std.echo output="foo"
              wait-before: 3
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf', {})

        self.engine.pause_workflow(wf_ex.id)

        self.await_workflow_paused(wf_ex.id)

        self.engine.stop_workflow(
            wf_ex.id,
            states.CANCELLED,
            "Cancelled by user."
        )

        self.await_workflow_cancelled(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.await_task_success(task_1_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled by user.", wf_ex.state_info)
        self.assertEqual(1, len(wf_ex.task_executions))
        self.assertEqual(states.SUCCESS, task_1_ex.state)

    def test_cancel_completed_workflow(self):
        workflow = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Echo"
        """

        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        self.engine.stop_workflow(
            wf_ex.id,
            states.CANCELLED,
            "Cancelled by user."
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_1_ex = self._assert_single_item(
            wf_ex.task_executions,
            name='task1'
        )

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertIsNone(wf_ex.state_info)
        self.assertEqual(1, len(wf_ex.task_executions))
        self.assertEqual(states.SUCCESS, task_1_ex.state)

    def test_cancel_parent_workflow(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf:
              type: direct
              tasks:
                taskx:
                  workflow: subwf

            subwf:
              type: direct
              tasks:
                task1:
                  action: std.echo output="Echo"
                  on-complete:
                    - task2

                task2:
                  action: std.echo output="foo"
                  wait-before: 2
        """

        wb_service.create_workbook_v2(workbook)

        wf_ex = self.engine.start_workflow('wb.wf', {})

        self.engine.stop_workflow(
            wf_ex.id,
            states.CANCELLED,
            "Cancelled by user."
        )

        self.await_workflow_cancelled(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')

        self.await_task_cancelled(task_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')

        subwf_execs = db_api.get_workflow_executions(
            task_execution_id=task_ex.id
        )

        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled by user.", wf_ex.state_info)
        self.assertEqual(states.CANCELLED, task_ex.state)
        self.assertEqual("Cancelled by user.", task_ex.state_info)
        self.assertEqual(1, len(subwf_execs))
        self.assertEqual(states.CANCELLED, subwf_execs[0].state)
        self.assertEqual("Cancelled by user.", subwf_execs[0].state_info)

    def test_cancel_child_workflow(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf:
              type: direct
              tasks:
                taskx:
                  workflow: subwf

            subwf:
              type: direct
              tasks:
                task1:
                  action: std.echo output="Echo"
                  on-complete:
                    - task2

                task2:
                  action: std.echo output="foo"
                  wait-before: 3
        """

        wb_service.create_workbook_v2(workbook)

        self.engine.start_workflow('wb.wf', {})

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_ex = self._assert_single_item(wf_execs, name='wb.subwf')

        self.engine.stop_workflow(
            subwf_ex.id,
            states.CANCELLED,
            "Cancelled by user."
        )

        self.await_workflow_cancelled(subwf_ex.id)
        self.await_task_cancelled(task_ex.id)
        self.await_workflow_cancelled(wf_ex.id)

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_ex = self._assert_single_item(wf_execs, name='wb.subwf')

        self.assertEqual(states.CANCELLED, subwf_ex.state)
        self.assertEqual("Cancelled by user.", subwf_ex.state_info)
        self.assertEqual(states.CANCELLED, task_ex.state)
        self.assertIn("Cancelled by user.", task_ex.state_info)
        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled tasks: taskx", wf_ex.state_info)

    def test_cancel_with_items_parent_workflow(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf:
              type: direct
              tasks:
                taskx:
                  with-items: i in [1, 2]
                  workflow: subwf

            subwf:
              type: direct
              tasks:
                task1:
                  action: std.echo output="Echo"
                  on-complete:
                    - task2

                task2:
                  action: std.echo output="foo"
                  wait-before: 1
        """
        wb_service.create_workbook_v2(workbook)

        wf_ex = self.engine.start_workflow('wb.wf', {})

        self.engine.stop_workflow(
            wf_ex.id,
            states.CANCELLED,
            "Cancelled by user."
        )

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')

        self.await_workflow_cancelled(wf_ex.id)
        self.await_task_cancelled(task_ex.id)

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_exs = self._assert_multiple_items(wf_execs, 2, name='wb.subwf')

        self.assertEqual(states.CANCELLED, subwf_exs[0].state)
        self.assertEqual("Cancelled by user.", subwf_exs[0].state_info)
        self.assertEqual(states.CANCELLED, subwf_exs[1].state)
        self.assertEqual("Cancelled by user.", subwf_exs[1].state_info)
        self.assertEqual(states.CANCELLED, task_ex.state)
        self.assertIn("cancelled", task_ex.state_info)
        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled by user.", wf_ex.state_info)

    def test_cancel_with_items_child_workflow(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf:
              type: direct
              tasks:
                taskx:
                  with-items: i in [1, 2]
                  workflow: subwf

            subwf:
              type: direct
              tasks:
                task1:
                  action: std.echo output="Echo"
                  on-complete:
                    - task2

                task2:
                  action: std.echo output="foo"
                  wait-before: 1
        """

        wb_service.create_workbook_v2(workbook)

        self.engine.start_workflow('wb.wf', {})

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_exs = self._assert_multiple_items(wf_execs, 2, name='wb.subwf')

        self.engine.stop_workflow(
            subwf_exs[0].id,
            states.CANCELLED,
            "Cancelled by user."
        )

        self.await_workflow_cancelled(subwf_exs[0].id)
        self.await_workflow_success(subwf_exs[1].id)
        self.await_task_cancelled(task_ex.id)
        self.await_workflow_cancelled(wf_ex.id)

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_exs = self._assert_multiple_items(wf_execs, 2, name='wb.subwf')

        self.assertEqual(states.CANCELLED, subwf_exs[0].state)
        self.assertEqual("Cancelled by user.", subwf_exs[0].state_info)
        self.assertEqual(states.SUCCESS, subwf_exs[1].state)
        self.assertIsNone(subwf_exs[1].state_info)
        self.assertEqual(states.CANCELLED, task_ex.state)
        self.assertIn("cancelled", task_ex.state_info)
        self.assertEqual(states.CANCELLED, wf_ex.state)
        self.assertEqual("Cancelled tasks: taskx", wf_ex.state_info)

    def test_cancel_then_fail_with_items_child_workflow(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf:
              type: direct
              tasks:
                taskx:
                  with-items: i in [1, 2]
                  workflow: subwf

            subwf:
              type: direct
              tasks:
                task1:
                  action: std.echo output="Echo"
                  on-complete:
                    - task2

                task2:
                  action: std.echo output="foo"
                  wait-before: 1
        """

        wb_service.create_workbook_v2(workbook)

        self.engine.start_workflow('wb.wf', {})

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_exs = self._assert_multiple_items(wf_execs, 2, name='wb.subwf')

        self.engine.stop_workflow(
            subwf_exs[0].id,
            states.CANCELLED,
            "Cancelled by user."
        )

        self.engine.stop_workflow(
            subwf_exs[1].id,
            states.ERROR,
            "Failed by user."
        )

        self.await_workflow_cancelled(subwf_exs[0].id)
        self.await_workflow_error(subwf_exs[1].id)
        self.await_task_error(task_ex.id)
        self.await_workflow_error(wf_ex.id)

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_exs = self._assert_multiple_items(wf_execs, 2, name='wb.subwf')

        self.assertEqual(states.CANCELLED, subwf_exs[0].state)
        self.assertEqual("Cancelled by user.", subwf_exs[0].state_info)
        self.assertEqual(states.ERROR, subwf_exs[1].state)
        self.assertEqual("Failed by user.", subwf_exs[1].state_info)
        self.assertEqual(states.ERROR, task_ex.state)
        self.assertIn("failed", task_ex.state_info)
        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn("Failed by user.", wf_ex.state_info)

    def test_fail_then_cancel_with_items_child_workflow(self):
        workbook = """
        version: '2.0'

        name: wb

        workflows:
            wf:
              type: direct
              tasks:
                taskx:
                  with-items: i in [1, 2]
                  workflow: subwf

            subwf:
              type: direct
              tasks:
                task1:
                  action: std.echo output="Echo"
                  on-complete:
                    - task2

                task2:
                  action: std.echo output="foo"
                  wait-before: 1
        """

        wb_service.create_workbook_v2(workbook)

        self.engine.start_workflow('wb.wf', {})

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_exs = self._assert_multiple_items(wf_execs, 2, name='wb.subwf')

        self.engine.stop_workflow(
            subwf_exs[1].id,
            states.ERROR,
            "Failed by user."
        )

        self.engine.stop_workflow(
            subwf_exs[0].id,
            states.CANCELLED,
            "Cancelled by user."
        )

        self.await_workflow_cancelled(subwf_exs[0].id)
        self.await_workflow_error(subwf_exs[1].id)
        self.await_task_error(task_ex.id)
        self.await_workflow_error(wf_ex.id)

        wf_execs = db_api.get_workflow_executions()

        wf_ex = self._assert_single_item(wf_execs, name='wb.wf')
        task_ex = self._assert_single_item(wf_ex.task_executions, name='taskx')
        subwf_exs = self._assert_multiple_items(wf_execs, 2, name='wb.subwf')

        self.assertEqual(states.CANCELLED, subwf_exs[0].state)
        self.assertEqual("Cancelled by user.", subwf_exs[0].state_info)
        self.assertEqual(states.ERROR, subwf_exs[1].state)
        self.assertEqual("Failed by user.", subwf_exs[1].state_info)
        self.assertEqual(states.ERROR, task_ex.state)
        self.assertIn("failed", task_ex.state_info)
        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn("Failed by user.", wf_ex.state_info)
