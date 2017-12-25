# Copyright 2016 - Nokia, Inc.
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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK_WITH_EXPRESSIONS = """
---
version: '2.0'

name: wb

workflows:
  test_tasks_function:
    input:
      - wf1_wx_id
      - wf2_wx_id
      - wf3_wx_id
      - wf4_wx_id
      - wf5_wx_id

    tasks:
      main_task:
        action: std.noop
        publish:
          all_tasks_yaql: <% tasks() %>
          all_tasks_jinja: "{{ tasks() }}"

          wf1_tasks_yaql: <% tasks($.wf1_wx_id) %>
          wf1_tasks_jinja: "{{ tasks(_.wf1_wx_id) }}"
          wf1_recursive_tasks_yaql: <% tasks($.wf1_wx_id, true) %>
          wf1_recursive_tasks_jinja: "{{ tasks(_.wf1_wx_id, true) }}"
          wf1_recursive_error_tasks_yaql: <% tasks($.wf1_wx_id, true, ERROR) %>
          wf1_recursive_error_tasks_jinja:
            "{{ tasks(_.wf1_wx_id, True, 'ERROR') }}"
          wf1_not_recursive_error_tasks_yaql:
            <% tasks($.wf1_wx_id, false, ERROR) %>
          wf1_not_recursive_error_tasks_jinja:
            "{{ tasks(_.wf1_wx_id, False, 'ERROR') }}"
          wf1_recursive_success_flat_tasks_yaql:
            <% tasks($.wf1_wx_id, true, SUCCESS, true) %>
          wf1_recursive_success_flat_tasks_jinja:
            "{{ tasks(_.wf1_wx_id, True, 'SUCCESS', True) }}"

          wf2_recursive_tasks_yaql: <% tasks($.wf2_wx_id, true) %>
          wf2_recursive_tasks_jinja: "{{ tasks(_.wf2_wx_id, true) }}"

          wf3_recursive_error_tasks_yaql: <% tasks($.wf3_wx_id, true, ERROR) %>
          wf3_recursive_error_tasks_jinja:
            "{{ tasks(_.wf3_wx_id, True, 'ERROR') }}"
          wf3_recursive_error_flat_tasks_yaql:
            <% tasks($.wf3_wx_id, true, ERROR, true) %>
          wf3_recursive_error_flat_tasks_jinja:
            "{{ tasks(_.wf3_wx_id, True, 'ERROR', True) }}"

          wf4_recursive_error_flat_tasks_yaql:
            <% tasks($.wf4_wx_id, true, ERROR, true) %>
          wf4_recursive_error_flat_tasks_jinja:
            "{{ tasks(_.wf4_wx_id, True, 'ERROR', True) }}"


          wf5_recursive_error_flat_tasks_yaql:
            <% tasks($.wf5_wx_id, true, ERROR, true) %>
          wf5_recursive_error_flat_tasks_jinja:
            "{{ tasks(_.wf5_wx_id, True, 'ERROR', True) }}"


  wf1_top_lvl:
    tasks:
      top_lvl_wf1_task_1:
        workflow: wf1_second_lvl

      top_lvl_wf1_task_2:
        action: std.noop

  wf1_second_lvl:
    tasks:
      second_lvl_wf1_task_1:
        workflow: wf1_third_lvl_fail
        on-error:
          - second_lvl_wf1_task_2

      second_lvl_wf1_task_2:
        action: std.noop

      second_lvl_wf1_task_3:
        action: std.noop

  wf1_third_lvl_fail:
    tasks:
      third_lvl_wf1_task_1:
        action: std.noop
        on-success:
          - third_lvl_wf1_task_2_fail

      third_lvl_wf1_task_2_fail:
        action: std.fail

      third_lvl_wf1_task_3:
        action: std.noop


  wf2_top_lvl:
    tasks:
      top_lvl_wf2_task_1:
        action: std.noop

      top_lvl_wf2_task_2:
        action: std.noop


  wf3_top_lvl:
    tasks:
      top_lvl_wf3_task_1_fail:
        workflow: wf3_second_lvl_fail

      top_lvl_wf3_task_2_fail:
        action: std.fail

  wf3_second_lvl_fail:
    tasks:
      second_lvl_wf3_task_1_fail:
        workflow: wf3_third_lvl_fail

      second_lvl_wf3_task_2:
        action: std.noop

      second_lvl_wf3_task_3:
        action: std.noop

  wf3_third_lvl_fail:
    tasks:
      third_lvl_wf3_task_1:
        action: std.noop
        on-success:
          - third_lvl_wf3_task_2

      third_lvl_wf3_task_2:
        action: std.noop

      third_lvl_wf3_task_3_fail:
        action: std.fail

  wf4_top_lvl:
    tasks:
      top_lvl_wf4_task_1:
        workflow: wf4_second_lvl
        publish:
          raise_error: <% $.invalid_yaql_expression %>

  wf4_second_lvl:
    tasks:
      second_lvl_wf4_task_1:
        action: std.noop

  wf5_top_lvl:
    tasks:
      top_lvl_wf5_task_1:
        workflow: wf4_second_lvl
        input:
          raise_error: <% $.invalid_yaql_expression2 %>

  wf5_second_lvl:
    tasks:
      second_lvl_wf5_task_1:
        workflow: wf5_third_lvl

  wf5_third_lvl:
    tasks:
      third_lvl_wf5_task_1:
        action: std.noop

"""


class TasksFunctionTest(base.EngineTestCase):
    def _assert_published_tasks(self, task, published_key,
                                expected_tasks_count=None,
                                expected_tasks_names=None):
        published = task.published[published_key]

        self.assertIsNotNone(
            published,
            "there is a problem with publishing '{}'".format(published_key)
        )

        published_names = [t['name'] for t in published]

        if expected_tasks_names:
            for e in expected_tasks_names:
                self.assertIn(e, published_names)

            if not expected_tasks_count:
                expected_tasks_count = len(expected_tasks_names)

        if expected_tasks_count:
            self.assertEqual(expected_tasks_count, len(published))

    def test_tasks_function(self):
        wb_service.create_workbook_v2(WORKBOOK_WITH_EXPRESSIONS)

        # Start helping workflow executions.
        wf1_ex = self.engine.start_workflow('wb.wf1_top_lvl')
        wf2_ex = self.engine.start_workflow('wb.wf2_top_lvl')
        wf3_ex = self.engine.start_workflow('wb.wf3_top_lvl')
        wf4_ex = self.engine.start_workflow('wb.wf4_top_lvl')
        wf5_ex = self.engine.start_workflow('wb.wf5_top_lvl')

        self.await_workflow_success(wf1_ex.id)
        self.await_workflow_success(wf2_ex.id)
        self.await_workflow_error(wf3_ex.id)
        self.await_workflow_error(wf4_ex.id)
        self.await_workflow_error(wf5_ex.id)

        # Start test workflow execution
        wf_ex = self.engine.start_workflow(
            'wb.test_tasks_function',
            wf_input={
                'wf1_wx_id': wf1_ex.id,
                'wf2_wx_id': wf2_ex.id,
                'wf3_wx_id': wf3_ex.id,
                'wf4_wx_id': wf4_ex.id,
                'wf5_wx_id': wf5_ex.id
            }
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertEqual(1, len(task_execs))

        main_task = task_execs[0]

        self._assert_published_tasks(main_task, 'all_tasks_yaql', 22)
        self._assert_published_tasks(main_task, 'all_tasks_jinja', 22)
        self._assert_published_tasks(
            main_task,
            'wf1_tasks_yaql',
            2,
            ['top_lvl_wf1_task_1', 'top_lvl_wf1_task_2']
        )

        self._assert_published_tasks(
            main_task,
            'wf1_tasks_jinja',
            2,
            ['top_lvl_wf1_task_1', 'top_lvl_wf1_task_2']
        )

        self._assert_published_tasks(
            main_task,
            'wf1_recursive_tasks_yaql',
            8,
            [
                'top_lvl_wf1_task_1',
                'top_lvl_wf1_task_2',
                'second_lvl_wf1_task_3',
                'second_lvl_wf1_task_1',
                'second_lvl_wf1_task_2',
                'third_lvl_wf1_task_3',
                'third_lvl_wf1_task_1',
                'third_lvl_wf1_task_2_fail'
            ]
        )

        self._assert_published_tasks(
            main_task,
            'wf1_recursive_tasks_jinja',
            8,
            [
                'top_lvl_wf1_task_1',
                'top_lvl_wf1_task_2',
                'second_lvl_wf1_task_3',
                'second_lvl_wf1_task_1',
                'second_lvl_wf1_task_2',
                'third_lvl_wf1_task_3',
                'third_lvl_wf1_task_1',
                'third_lvl_wf1_task_2_fail'
            ]
        )

        self._assert_published_tasks(
            main_task,
            'wf1_recursive_error_tasks_yaql',
            2,
            ['second_lvl_wf1_task_1', 'third_lvl_wf1_task_2_fail']
        )

        self._assert_published_tasks(
            main_task,
            'wf1_recursive_error_tasks_jinja',
            2,
            ['second_lvl_wf1_task_1', 'third_lvl_wf1_task_2_fail']
        )

        self._assert_published_tasks(
            main_task,
            'wf1_not_recursive_error_tasks_yaql',
            0
        )

        self._assert_published_tasks(
            main_task,
            'wf1_not_recursive_error_tasks_jinja',
            0
        )

        self._assert_published_tasks(
            main_task,
            'wf1_recursive_success_flat_tasks_yaql',
            5,
            [
                'top_lvl_wf1_task_2',
                'second_lvl_wf1_task_3',
                'second_lvl_wf1_task_2',
                'third_lvl_wf1_task_3',
                'third_lvl_wf1_task_1'
            ]
        )

        self._assert_published_tasks(
            main_task,
            'wf1_recursive_success_flat_tasks_jinja',
            5,
            [
                'top_lvl_wf1_task_2',
                'second_lvl_wf1_task_3',
                'second_lvl_wf1_task_2',
                'third_lvl_wf1_task_3',
                'third_lvl_wf1_task_1'
            ]
        )

        self._assert_published_tasks(
            main_task,
            'wf2_recursive_tasks_yaql',
            2,
            ['top_lvl_wf2_task_2', 'top_lvl_wf2_task_1']
        )

        self._assert_published_tasks(
            main_task,
            'wf2_recursive_tasks_jinja',
            2,
            ['top_lvl_wf2_task_2', 'top_lvl_wf2_task_1']
        )

        self._assert_published_tasks(
            main_task,
            'wf3_recursive_error_tasks_yaql',
            4,
            [
                'top_lvl_wf3_task_1_fail',
                'top_lvl_wf3_task_2_fail',
                'second_lvl_wf3_task_1_fail',
                'third_lvl_wf3_task_3_fail'
            ]
        )

        self._assert_published_tasks(
            main_task,
            'wf3_recursive_error_tasks_jinja',
            4,
            [
                'top_lvl_wf3_task_1_fail',
                'top_lvl_wf3_task_2_fail',
                'second_lvl_wf3_task_1_fail',
                'third_lvl_wf3_task_3_fail'
            ]
        )

        self._assert_published_tasks(
            main_task,
            'wf3_recursive_error_flat_tasks_yaql',
            2,
            ['top_lvl_wf3_task_2_fail', 'third_lvl_wf3_task_3_fail']
        )

        self._assert_published_tasks(
            main_task,
            'wf3_recursive_error_flat_tasks_jinja',
            2,
            ['top_lvl_wf3_task_2_fail', 'third_lvl_wf3_task_3_fail']
        )

        self._assert_published_tasks(
            main_task,
            'wf4_recursive_error_flat_tasks_yaql',
            1,
            ['top_lvl_wf4_task_1']
        )

        self._assert_published_tasks(
            main_task,
            'wf4_recursive_error_flat_tasks_jinja',
            1,
            ['top_lvl_wf4_task_1']
        )

        self._assert_published_tasks(
            main_task,
            'wf5_recursive_error_flat_tasks_yaql',
            1,
            ['top_lvl_wf5_task_1']
        )

        self._assert_published_tasks(
            main_task,
            'wf5_recursive_error_flat_tasks_jinja',
            1,
            ['top_lvl_wf5_task_1']
        )
