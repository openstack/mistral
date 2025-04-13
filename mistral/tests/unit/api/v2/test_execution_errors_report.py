# Copyright 2022 - NetCracker Technology Corp.
# Modified in 2025 by NetCracker Technology Corp.
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

from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.api import base
from mistral.tests.unit.engine import base as engine_base


class TestErrorsReportController(base.APITest, engine_base.EngineTestCase):
    def test_wf_without_errors(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_success(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        self.assertIn('errors', resp.json)
        errors = resp.json['errors']
        self.assertEqual(0, len(errors))

    def test_wf_with_handled_error(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              action: std.fail
              on-error: task2
            task2:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_success(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        self.assertIn('errors', resp.json)
        errors = resp.json['errors']
        self.assertEqual(0, len(errors))

    def test_wf_with_action_error(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              action: std.fail
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        errors = resp.json['errors']
        self.assertEqual(3, len(errors))

        wf_error_obj = self._assert_single_item(
            errors,
            name='wf',
            type='WORKFLOW',
            parent_id=None,
            error='Failure caused by error in tasks: task1'
        )

        task_error_obj = self._assert_single_item(
            errors,
            name='task1',
            type='TASK',
            parent_id=wf_error_obj['id'],
            error='The action raised an exception'
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.'
        )

    def test_wf_with_task_timeout(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              action: std.sleep seconds=3
              timeout: 1
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        errors = resp.json['errors']
        self.assertEqual(3, len(errors))

        wf_error_obj = self._assert_single_item(
            errors,
            name='wf',
            type='WORKFLOW',
            parent_id=None,
            error='Failure caused by error in tasks: task1'
        )

        task_error_obj = self._assert_single_item(
            errors,
            name='task1',
            type='TASK',
            parent_id=wf_error_obj['id'],
            error='The action raised an exception'
        )

        self._assert_single_item(
            errors,
            name='std.sleep',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Action timed out'
        )

    def test_wf_with_task_fail_on(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              action: std.noop
              fail-on: '<% True %>'
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        errors = resp.json['errors']
        self.assertEqual(2, len(errors))

        wf_error_obj = self._assert_single_item(
            errors,
            name='wf',
            type='WORKFLOW',
            parent_id=None,
            error='Failure caused by error in tasks: task1'
        )

        self._assert_single_item(
            errors,
            name='task1',
            type='TASK',
            parent_id=wf_error_obj['id'],
            error="Failed by 'fail-on' policy"
        )

    def test_wf_with_subwf_fail(self):
        wb_text = """---
        version: '2.0'
        name: wb
        workflows:
          parent_wf:
            tasks:
              task1:
                workflow: child_wf

          child_wf:
            tasks:
              task1:
                action:
                  std.fail
        """

        wb_service.create_workbook_v2(wb_text)
        wf_ex = self.engine.start_workflow('wb.parent_wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        errors = resp.json['errors']
        self.assertEqual(5, len(errors))

        wf_error_obj = self._assert_single_item(
            errors,
            name='wb.parent_wf',
            type='WORKFLOW',
            parent_id=None,
            error='Failure caused by error in tasks: task1'
        )

        task_error_obj = self._assert_single_item(
            errors,
            name='task1',
            type='TASK',
            parent_id=wf_error_obj['id'],
            error='Failure caused by error in tasks: task1'
        )

        subwf_error_obj = self._assert_single_item(
            errors,
            name='wb.child_wf',
            type='WORKFLOW',
            parent_id=task_error_obj['id'],
            error='Failure caused by error in tasks: task1'
        )

        task_error_obj = self._assert_single_item(
            errors,
            name='task1',
            type='TASK',
            parent_id=subwf_error_obj['id'],
            error='The action raised an exception'
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.'
        )

    def test_wf_with_with_items_task(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              action: std.fail
              with-items: 'v in <% [1,2,3] %>'
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        errors = resp.json['errors']
        self.assertEqual(5, len(errors))

        wf_error_obj = self._assert_single_item(
            errors,
            name='wf',
            type='WORKFLOW',
            parent_id=None,
            error='Failure caused by error in tasks: task1'
        )

        task_error_obj = self._assert_single_item(
            errors,
            name='task1',
            type='TASK',
            parent_id=wf_error_obj['id'],
            error='One or more actions had failed.'
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.',
            idx=0
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.',
            idx=1
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.',
            idx=2
        )

    def test_wf_with_task_retries(self):
        wf_text = """---
        version: '2.0'
        wf:
          tasks:
            task1:
              action: std.fail
              retry:
                count: 2
                delay: 0
        """

        wf_service.create_workflows(wf_text)
        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/errors_report' % wf_ex.id)
        self.assertEqual(200, resp.status_int)

        errors = resp.json['errors']
        self.assertEqual(5, len(errors))

        wf_error_obj = self._assert_single_item(
            errors,
            name='wf',
            type='WORKFLOW',
            parent_id=None,
            error='Failure caused by error in tasks: task1'
        )

        task_error_obj = self._assert_single_item(
            errors,
            name='task1',
            type='TASK',
            parent_id=wf_error_obj['id'],
            error='The action raised an exception'
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.',
            idx=0
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.',
            idx=1
        )

        self._assert_single_item(
            errors,
            name='std.fail',
            type='ACTION',
            parent_id=task_error_obj['id'],
            error='Fail action expected exception.',
            idx=2
        )
