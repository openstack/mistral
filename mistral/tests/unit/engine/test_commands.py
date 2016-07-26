# Copyright 2014 - Mirantis, Inc.
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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK1 = """
---
version: '2.0'

name: my_wb

workflows:
  wf:
    type: direct
    input:
      - my_var

    tasks:
      task1:
        action: std.echo output='1'
        on-complete:
          - fail: <% $.my_var = 1 %>
          - succeed: <% $.my_var = 2 %>
          - pause: <% $.my_var = 3 %>
          - task2

      task2:
        action: std.echo output='2'
"""


class SimpleEngineCommandsTest(base.EngineTestCase):
    def setUp(self):
        super(SimpleEngineCommandsTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK1)

    def test_fail(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 1})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

    def test_succeed(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 2})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

    def test_pause(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 3})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )


WORKBOOK2 = """
---
version: '2.0'

name: my_wb

workflows:
  wf:
    type: direct
    input:
      - my_var

    task-defaults:
      on-complete:
        - fail: <% $.my_var = 1 %>
        - succeed: <% $.my_var = 2 %>
        - pause: <% $.my_var = 3 %>
        - task2: <% $.my_var = 4 %> # (Never happens in this test)

    tasks:
      task1:
        action: std.echo output='1'

      task2:
        action: std.echo output='2'
"""


class SimpleEngineWorkflowLevelCommandsTest(base.EngineTestCase):
    def setUp(self):
        super(SimpleEngineWorkflowLevelCommandsTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK2)

    def test_fail(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 1})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

    def test_succeed(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 2})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

    def test_pause(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 3})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )


WORKBOOK3 = """
---
version: '2.0'

name: my_wb

workflows:
  fail_first_wf:
    type: direct

    tasks:
      task1:
        action: std.echo output='1'
        on-complete:
          - fail
          - task2

      task2:
        action: std.echo output='2'

  fail_second_wf:
    type: direct

    tasks:
      task1:
        action: std.echo output='1'
        on-complete:
          - task2
          - fail

      task2:
        action: std.echo output='2'

  succeed_first_wf:
    type: direct

    tasks:
      task1:
        action: std.echo output='1'
        on-complete:
          - succeed
          - task2

      task2:
        action: std.echo output='2'

  succeed_second_wf:
    type: direct

    tasks:
      task1:
        action: std.echo output='1'
        on-complete:
          - task2
          - succeed

      task2:
        action: std.http url='some.not.existing.url'
"""


class OrderEngineCommandsTest(base.EngineTestCase):
    def setUp(self):
        super(OrderEngineCommandsTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK3)

    def test_fail_first(self):
        wf_ex = self.engine.start_workflow('my_wb.fail_first_wf', None)

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

    def test_fail_second(self):
        wf_ex = self.engine.start_workflow('my_wb.fail_second_wf', None)

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        task2_db = self._assert_single_item(
            wf_ex.task_executions,
            name='task2'
        )

        self.await_task_success(task2_db.id)
        self.await_workflow_error(wf_ex.id)

    def test_succeed_first(self):
        wf_ex = self.engine.start_workflow('my_wb.succeed_first_wf', None)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )

    def test_succeed_second(self):
        wf_ex = self.engine.start_workflow('my_wb.succeed_second_wf', None)

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(2, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        task2_db = self._assert_single_item(
            wf_ex.task_executions,
            name='task2'
        )

        self.await_task_error(task2_db.id)
        self.await_workflow_success(wf_ex.id)

WORKBOOK4 = """
---
version: '2.0'

name: my_wb

workflows:
  wf:
    type: direct
    input:
      - my_var

    tasks:
      task1:
        action: std.echo output='1'
        on-complete:
        - fail(msg='my_var value is 1'): <% $.my_var = 1 %>
        - succeed(msg='my_var value is 2'): <% $.my_var = 2 %>
        - pause(msg='my_var value is 3'): <% $.my_var = 3 %>
        - task2

      task2:
        action: std.echo output='2'
"""


class SimpleEngineCmdsWithMsgTest(base.EngineTestCase):
    def setUp(self):
        super(SimpleEngineCmdsWithMsgTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK4)

    def test_fail(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 1})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual('my_var value is 1', wf_ex.state_info)

    def test_succeed(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 2})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual("my_var value is 2", wf_ex.state_info)

    def test_pause(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 3})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual("my_var value is 3", wf_ex.state_info)

WORKBOOK5 = """
---
version: '2.0'

name: my_wb

workflows:
  wf:
    type: direct
    input:
      - my_var

    task-defaults:
      on-complete:
        - fail(msg='my_var value is 1'): <% $.my_var = 1 %>
        - succeed(msg='my_var value is <% $.my_var %>'): <% $.my_var = 2 %>
        - pause(msg='my_var value is 3'): <% $.my_var = 3 %>
        - task2: <% $.my_var = 4 %> # (Never happens in this test)

    tasks:
      task1:
        action: std.echo output='1'

      task2:
        action: std.echo output='2'
"""


class SimpleEngineWorkflowLevelCmdsWithMsgTest(base.EngineTestCase):
    def setUp(self):
        super(SimpleEngineWorkflowLevelCmdsWithMsgTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK5)

    def test_fail(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 1})

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertEqual("my_var value is 1", wf_ex.state_info)

    def test_succeed(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 2})

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual("my_var value is 2", wf_ex.state_info)

    def test_pause(self):
        wf_ex = self.engine.start_workflow('my_wb.wf', {'my_var': 3})

        self.await_workflow_paused(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(1, len(wf_ex.task_executions))
        self._assert_single_item(
            wf_ex.task_executions,
            name='task1',
            state=states.SUCCESS
        )
        self.assertEqual(states.PAUSED, wf_ex.state)
        self.assertEqual("my_var value is 3", wf_ex.state_info)
