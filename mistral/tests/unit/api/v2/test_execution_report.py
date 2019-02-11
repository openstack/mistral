# Copyright 2019 - Nokia Networks, Inc.
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
from mistral.workflow import states


class TestExecutionReportController(base.APITest, engine_base.EngineTestCase):
    def test_simple_sequence_wf(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              on-success: task2

            task2:
              action: std.fail
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/report' % wf_ex.id)

        self.assertEqual(200, resp.status_int)

        # Now let's verify the response structure

        self.assertIn('root_workflow_execution', resp.json)

        root_wf_ex = resp.json['root_workflow_execution']

        self.assertIsInstance(root_wf_ex, dict)
        self.assertEqual(wf_ex.id, root_wf_ex['id'])
        self.assertEqual(wf_ex.name, root_wf_ex['name'])
        self.assertEqual(states.ERROR, root_wf_ex['state'])
        self.assertGreater(len(root_wf_ex['state_info']), 0)

        tasks = root_wf_ex['task_executions']

        self.assertIsInstance(tasks, list)

        self.assertEqual(2, len(tasks))

        # Verify task1 info.
        task1 = self._assert_single_item(
            tasks,
            name='task1',
            state=states.SUCCESS
        )

        self.assertEqual(0, len(task1['workflow_executions']))
        self.assertEqual(1, len(task1['action_executions']))

        task1_action = task1['action_executions'][0]

        self.assertEqual(states.SUCCESS, task1_action['state'])
        self.assertEqual('std.noop', task1_action['name'])

        # Verify task2 info.
        task2 = self._assert_single_item(
            tasks,
            name='task2',
            state=states.ERROR
        )

        self.assertEqual(1, len(task2['action_executions']))

        task2_action = task2['action_executions'][0]

        self.assertEqual(0, len(task2['workflow_executions']))
        self.assertEqual(states.ERROR, task2_action['state'])

        # Verify statistics.
        stat = resp.json['statistics']

        self.assertEqual(1, stat['error_tasks_count'])
        self.assertEqual(0, stat['idle_tasks_count'])
        self.assertEqual(0, stat['paused_tasks_count'])
        self.assertEqual(0, stat['running_tasks_count'])
        self.assertEqual(1, stat['success_tasks_count'])
        self.assertEqual(2, stat['total_tasks_count'])

    def test_nested_wf(self):
        wb_text = """---
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

        wb_service.create_workbook_v2(wb_text)

        wf_ex = self.engine.start_workflow('wb.parent_wf')

        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/report' % wf_ex.id)

        self.assertEqual(200, resp.status_int)

        # Now let's verify the response structure

        self.assertIn('root_workflow_execution', resp.json)

        root_wf_ex = resp.json['root_workflow_execution']

        self.assertIsInstance(root_wf_ex, dict)
        self.assertEqual('wb.parent_wf', root_wf_ex['name'])
        self.assertEqual(states.ERROR, root_wf_ex['state'])
        self.assertGreater(len(root_wf_ex['state_info']), 0)

        tasks = root_wf_ex['task_executions']

        self.assertIsInstance(tasks, list)

        self.assertEqual(2, len(tasks))

        # Verify task1 info.
        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(states.SUCCESS, task1['state'])
        self.assertEqual(0, len(task1['workflow_executions']))
        self.assertEqual(1, len(task1['action_executions']))

        task1_action = task1['action_executions'][0]
        self.assertEqual(states.SUCCESS, task1_action['state'])
        self.assertEqual('std.noop', task1_action['name'])

        # Verify task2 info.
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(states.ERROR, task2['state'])
        self.assertEqual(0, len(task2['action_executions']))
        self.assertEqual(1, len(task2['workflow_executions']))

        sub_wf_entry = task2['workflow_executions'][0]
        self.assertEqual(states.ERROR, sub_wf_entry['state'])

        sub_wf_tasks = sub_wf_entry['task_executions']

        self.assertEqual(2, len(sub_wf_tasks))

        sub_wf_task1 = self._assert_single_item(
            sub_wf_tasks,
            name='task1',
            state=states.SUCCESS
        )
        sub_wf_task2 = self._assert_single_item(
            sub_wf_tasks,
            name='task2',
            state=states.ERROR
        )

        self.assertEqual(1, len(sub_wf_task1['action_executions']))
        self.assertEqual(
            states.SUCCESS,
            sub_wf_task1['action_executions'][0]['state']
        )

        self.assertEqual(1, len(sub_wf_task2['action_executions']))
        self.assertEqual(
            states.ERROR,
            sub_wf_task2['action_executions'][0]['state']
        )

        # Verify statistics.
        stat = resp.json['statistics']

        self.assertEqual(2, stat['error_tasks_count'])
        self.assertEqual(0, stat['idle_tasks_count'])
        self.assertEqual(0, stat['paused_tasks_count'])
        self.assertEqual(0, stat['running_tasks_count'])
        self.assertEqual(2, stat['success_tasks_count'])
        self.assertEqual(4, stat['total_tasks_count'])

    def test_nested_wf_errors_only(self):
        wb_text = """---
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

        wb_service.create_workbook_v2(wb_text)

        wf_ex = self.engine.start_workflow('wb.parent_wf')

        self.await_workflow_error(wf_ex.id)

        resp = self.app.get(
            '/v2/executions/%s/report?errors_only=true' % wf_ex.id
        )

        self.assertEqual(200, resp.status_int)

        # Now let's verify the response structure

        self.assertIn('root_workflow_execution', resp.json)

        root_wf_ex = resp.json['root_workflow_execution']

        self.assertIsInstance(root_wf_ex, dict)
        self.assertEqual('wb.parent_wf', root_wf_ex['name'])
        self.assertEqual(states.ERROR, root_wf_ex['state'])
        self.assertGreater(len(root_wf_ex['state_info']), 0)

        tasks = root_wf_ex['task_executions']

        self.assertIsInstance(tasks, list)

        self.assertEqual(1, len(tasks))

        # There must be only task2 in the response.
        # Verify task2 info.
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(states.ERROR, task2['state'])
        self.assertEqual(0, len(task2['action_executions']))
        self.assertEqual(1, len(task2['workflow_executions']))

        sub_wf_entry = task2['workflow_executions'][0]
        self.assertEqual(states.ERROR, sub_wf_entry['state'])

        sub_wf_tasks = sub_wf_entry['task_executions']

        self.assertEqual(1, len(sub_wf_tasks))

        sub_wf_task2 = self._assert_single_item(
            sub_wf_tasks,
            name='task2',
            state=states.ERROR
        )

        self.assertEqual(1, len(sub_wf_task2['action_executions']))
        self.assertEqual(
            states.ERROR,
            sub_wf_task2['action_executions'][0]['state']
        )

        # Verify statistics.
        stat = resp.json['statistics']

        self.assertEqual(2, stat['error_tasks_count'])
        self.assertEqual(0, stat['idle_tasks_count'])
        self.assertEqual(0, stat['paused_tasks_count'])
        self.assertEqual(0, stat['running_tasks_count'])
        self.assertEqual(0, stat['success_tasks_count'])
        self.assertEqual(2, stat['total_tasks_count'])

    def test_nested_wf_max_depth(self):
        wb_text = """---
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

        wb_service.create_workbook_v2(wb_text)

        wf_ex = self.engine.start_workflow('wb.parent_wf')

        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/report?max_depth=0' % wf_ex.id)

        self.assertEqual(200, resp.status_int)

        # Now let's verify the response structure

        self.assertIn('root_workflow_execution', resp.json)

        root_wf_ex = resp.json['root_workflow_execution']

        self.assertIsInstance(root_wf_ex, dict)
        self.assertEqual('wb.parent_wf', root_wf_ex['name'])
        self.assertEqual(states.ERROR, root_wf_ex['state'])
        self.assertGreater(len(root_wf_ex['state_info']), 0)

        tasks = root_wf_ex['task_executions']

        self.assertIsInstance(tasks, list)

        self.assertEqual(2, len(tasks))

        # Verify task1 info.
        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(states.SUCCESS, task1['state'])
        self.assertEqual(0, len(task1['workflow_executions']))
        self.assertEqual(1, len(task1['action_executions']))

        task1_action = task1['action_executions'][0]
        self.assertEqual(states.SUCCESS, task1_action['state'])
        self.assertEqual('std.noop', task1_action['name'])

        # Verify task2 info.
        task2 = self._assert_single_item(tasks, name='task2')

        self.assertEqual(states.ERROR, task2['state'])
        self.assertEqual(0, len(task2['action_executions']))
        self.assertEqual(1, len(task2['workflow_executions']))

        sub_wf_entry = task2['workflow_executions'][0]
        self.assertEqual(states.ERROR, sub_wf_entry['state'])

        # We still must have an entry for the subworkflow itself
        # but it must not have info about task executions because
        # we've now limited max depth.
        self.assertNotIn('task_executions', sub_wf_entry)

        # Verify statistics.
        stat = resp.json['statistics']

        self.assertEqual(1, stat['error_tasks_count'])
        self.assertEqual(0, stat['idle_tasks_count'])
        self.assertEqual(0, stat['paused_tasks_count'])
        self.assertEqual(0, stat['running_tasks_count'])
        self.assertEqual(1, stat['success_tasks_count'])
        self.assertEqual(2, stat['total_tasks_count'])
