# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from oslo_config import cfg
import testtools

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class JoinEngineTest(base.EngineTestCase):
    def test_full_join_simple(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          tasks:
            join_task:
              join: all

            task1:
              on-success: join_task

            task2:
              on-success: join_task
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

    def test_full_join_without_errors(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          output:
            result: <% $.result3 %>

          tasks:
            task1:
              action: std.echo output=1
              publish:
                result1: <% task(task1).result %>
              on-complete:
                - task3

            task2:
              action: std.echo output=2
              publish:
                result2: <% task(task2).result %>
              on-complete:
                - task3

            task3:
              join: all
              action: std.echo output="<% $.result1 %>,<% $.result2 %>"
              publish:
                result3: <% task(task3).result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual({'result': '1,2'}, wf_ex.output)

            tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)
        self.assertEqual(states.SUCCESS, task3.state)

    def test_full_join_with_errors(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          output:
            result: <% $.result3 %>

          tasks:
            task1:
              action: std.echo output=1
              publish:
                result1: <% task(task1).result %>
              on-complete:
                - task3

            task2:
              action: std.fail
              on-error:
                - task3

            task3:
              join: all
              action: std.echo output="<% $.result1 %>-<% $.result1 %>"
              publish:
                result3: <% task(task3).result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual({'result': '1-1'}, wf_ex.output)

            tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.ERROR, task2.state)
        self.assertEqual(states.SUCCESS, task3.state)

    def test_full_join_with_conditions(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          output:
            result: <% $.result4 %>

          tasks:
            task1:
              action: std.echo output=1
              publish:
                result1: <% task(task1).result %>
              on-complete:
                - task3

            task2:
              action: std.echo output=2
              publish:
                result2: <% task(task2).result %>
              on-complete:
                - task3: <% $.result2 = 11111 %>
                - task4: <% $.result2 = 2 %>

            task3:
              join: all
              action: std.echo output="<% $.result1 %>-<% $.result1 %>"
              publish:
                result3: <% task(task3).result %>

            task4:
              action: std.echo output=4
              publish:
                result4: <% task(task4).result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self._await(
            lambda:
            len(db_api.get_workflow_execution(wf_ex.id).task_executions) == 4
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')
        task4 = self._assert_single_item(tasks, name='task4')

        # NOTE(xylan): We ensure task4 is successful here because of the
        # uncertainty of its running parallelly with task3.
        self.await_task_success(task4.id)

        self.assertEqual(states.RUNNING, wf_ex.state)
        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)
        self.assertEqual(states.WAITING, task3.state)

    def test_partial_join(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          output:
            result: <% $.result4 %>

          tasks:
            task1:
              action: std.echo output=1
              publish:
                result1: <% task(task1).result %>
              on-complete:
                - task4

            task2:
              action: std.echo output=2
              publish:
                result2: <% task(task2).result %>
              on-complete:
                - task4

            task3:
              action: std.fail
              description: |
                Always fails and 'on-success' never gets triggered.
                However, 'task4' will run since its join cardinality
                is 2 which means 'task1' and 'task2' completion is
                enough to trigger it.
              on-success:
                - task4
              on-error:
                - noop

            task4:
              join: 2
              action: std.echo output="<% $.result1 %>,<% $.result2 %>"
              publish:
                result4: <% task(task4).result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual({'result': '1,2'}, wf_ex.output)

            tasks = wf_ex.task_executions

        self.assertEqual(4, len(tasks))

        task4 = self._assert_single_item(tasks, name='task4')
        task1 = self._assert_single_item(tasks, name='task1')
        task2 = self._assert_single_item(tasks, name='task2')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual(states.SUCCESS, task2.state)
        self.assertEqual(states.SUCCESS, task4.state)

        # task3 may still be in RUNNING state and we need to make sure
        # it gets into ERROR state.
        self.await_task_error(task3.id)

        self.assertDictEqual({'result4': '1,2'}, task4.published)

    def test_partial_join_triggers_once(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          output:
            result: <% $.result5 %>

          tasks:
            task1:
              action: std.noop
              publish:
                result1: 1
              on-complete:
                - task5

            task2:
              action: std.noop
              publish:
                result2: 2
              on-complete:
                - task5

            task3:
              action: std.noop
              publish:
                result3: 3
              on-complete:
                - task5

            task4:
              action: std.noop
              publish:
                result4: 4
              on-complete:
                - task5

            task5:
              join: 2
              action: std.echo
              input:
                output: |
                  <% result1 in $.keys() %>,<% result2 in $.keys() %>,
                  <% result3 in $.keys() %>,<% result4 in $.keys() %>
              publish:
                result5: <% task(task5).result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        self.assertEqual(5, len(tasks))

        task5 = self._assert_single_item(tasks, name='task5')

        self.assertEqual(states.SUCCESS, task5.state)

        success_count = sum([1 for t in tasks if t.state == states.SUCCESS])

        # At least task4 and two others must be successfully completed.
        self.assertGreaterEqual(success_count, 3)

        result5 = task5.published['result5']

        self.assertIsNotNone(result5)

        # Depending on how many inbound tasks completed before 'join'
        # task5 started it can get different inbound context with.
        # But at least two inbound results should be accessible at task5
        # which logically corresponds to 'join' cardinality 2.
        self.assertGreaterEqual(result5.count('True'), 2)

    def test_discriminator(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          output:
            result: <% $.result4 %>

          tasks:
            task1:
              action: std.noop
              publish:
                result1: 1
              on-complete:
                - task4

            task2:
              action: std.noop
              publish:
                result2: 2
              on-complete:
                - task4

            task3:
              action: std.noop
              publish:
                result3: 3
              on-complete:
                - task4

            task4:
              join: one
              action: std.echo
              input:
                output: |
                  <% result1 in $.keys() %>,<% result2 in $.keys() %>,
                  <% result3 in $.keys() %>
              publish:
                result4: <% task(task4).result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        self.assertEqual(4, len(tasks))

        task4 = self._assert_single_item(tasks, name='task4')

        self.assertEqual(states.SUCCESS, task4.state)

        success_count = sum([1 for t in tasks if t.state == states.SUCCESS])

        # At least task4 and one of others must be successfully completed.
        self.assertGreaterEqual(success_count, 2)

        result4 = task4.published['result4']

        self.assertIsNotNone(result4)
        self.assertLess(result4.count('False'), 3)
        self.assertGreaterEqual(result4.count('True'), 1)

    def test_full_join_parallel_published_vars(self):
        wfs_tasks_join_complex = """---
        version: '2.0'

        main:
          type: direct

          output:
            var1: <% $.var1 %>
            var2: <% $.var2 %>
            is_done: <% $.is_done %>

          tasks:
            init:
              publish:
                var1: false
                var2: false
                is_done: false
              on-success:
                - branch1
                - branch2

            branch1:
              workflow: work
              publish:
                var1: true
              on-success:
                - done

            branch2:
              publish:
                var2: true
              on-success:
                - done

            done:
              join: all
              publish:
                is_done: true

        work:
          type: direct

          tasks:
            do:
              action: std.echo output="Doing..."
              on-success:
                - exit

            exit:
              action: std.echo output="Exiting..."
        """
        wf_service.create_workflows(wfs_tasks_join_complex)

        # Start workflow.
        wf_ex = self.engine.start_workflow('main', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual(
                {
                    'var1': True,
                    'is_done': True,
                    'var2': True
                },
                wf_ex.output
            )

    @testtools.skip('https://bugs.launchpad.net/mistral/+bug/1424461')
    def test_full_join_parallel_published_vars_complex(self):
        wf_text = """---
        version: "2.0"

        main:
          type: direct
          output:
            var_a: <% $.var_a %>
            var_b: <% $.var_b %>
            var_c: <% $.var_c %>
            var_d: <% $.var_d %>
          tasks:
            init:
              publish:
                var_a: 0
                var_b: 0
                var_c: 0
              on-success:
                - branch1_0
                - branch2_0

            branch1_0:
              publish:
                var_c: 1
              on-success:
                - branch1_1

            branch2_0:
              publish:
                var_a: 1
              on-success:
                - done

            branch1_1:
              publish:
                var_b: 1
              on-success:
                - done

            done:
              join: all
              publish:
                var_d: 1
        """
        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('main', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual(
                {
                    'var_a': 1,
                    'var_b': 1,
                    'var_c': 1,
                    'var_d': 1
                },
                wf_ex.output
            )

    def test_full_join_with_branch_errors(self):
        wf_text = """---
        version: '2.0'

        main:
          type: direct

          tasks:
            task10:
              action: std.noop
              on-success:
                - task21
                - task31

            task21:
              action: std.noop
              on-success:
                - task22

            task22:
              action: std.noop
              on-success:
                - task40

            task31:
              action: std.fail
              on-success:
                - task32

            task32:
              action: std.noop
              on-success:
                - task40

            task40:
              join: all
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('main', {})

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        self.assertIsNotNone(wf_ex.state_info)

        task10 = self._assert_single_item(tasks, name='task10')
        task21 = self._assert_single_item(tasks, name='task21')
        task22 = self._assert_single_item(tasks, name='task22')
        task31 = self._assert_single_item(tasks, name='task31')
        task40 = self._assert_single_item(tasks, name='task40')

        self.assertEqual(states.SUCCESS, task10.state)
        self.assertEqual(states.SUCCESS, task21.state)
        self.assertEqual(states.SUCCESS, task22.state)
        self.assertEqual(states.ERROR, task31.state)
        self.assertNotIn('task32', [task.name for task in tasks])
        self.assertEqual(states.ERROR, task40.state)

    def test_diamond_join_all(self):
        wf_text = """---
        version: '2.0'

        test-join:
          tasks:
            a:
              on-success:
                - b
                - c
                - d

            b:
              on-success:
                - e

            c:
              on-success:
                - e

            d:
              on-success:
                - e

            e:
              join: all
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('test-join', {})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        self._assert_multiple_items(tasks, 5, state=states.SUCCESS)

    def test_join_multiple_routes_with_one_source(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            a:
              on-success:
                - b
                - c

            b:
              on-success:
                - c

            c:
              join: all
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

            self._assert_multiple_items(tasks, 3, state=states.SUCCESS)

    def test_join_after_join(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            a:
              on-success:
                - c

            b:
              on-success:
                - c

            c:
              join: all
              on-success:
                - f

            d:
              on-success:
                - f

            e:
              on-success:
                - f

            f:
              join: all
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(6, len(task_execs))

        self._assert_multiple_items(task_execs, 6, state=states.SUCCESS)

    def test_join_route_delays(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            a:
              wait-before: 4
              on-success: b
            b:
              on-success: join

            c:
              on-success: join

            join:
              join: all
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(4, len(task_execs))

        self._assert_multiple_items(task_execs, 4, state=states.SUCCESS)

    def delete_join_completion_check_on_stop(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              on-success: join_task

            task2:
              description: Never ends
              action: std.async_noop
              on-success: join_task

            join_task:
              join: all
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        tasks = db_api.get_task_executions(workflow_execution_id=wf_ex.id)

        self.assertTrue(len(tasks) >= 2)

        task1 = self._assert_single_item(tasks, name='task1')

        self.await_task_success(task1.id)

        # Once task1 is finished we know that join_task must be created.

        tasks = db_api.get_task_executions(workflow_execution_id=wf_ex.id)

        self._assert_single_item(
            tasks,
            name='join_task',
            state=states.WAITING
        )

        calls = db_api.get_delayed_calls()

        mtd_name = 'mistral.engine.task_handler._refresh_task_state'

        self._assert_single_item(calls, target_method_name=mtd_name)

        # Stop the workflow.
        self.engine.stop_workflow(wf_ex.id, state=states.CANCELLED)

        self._await(
            lambda:
            len(db_api.get_delayed_calls(target_method_name=mtd_name)) == 0
        )

    def delete_join_completion_check_on_execution_delete(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              on-success: join_task

            task2:
              description: Never ends
              action: std.async_noop
              on-success: join_task

            join_task:
              join: all
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        tasks = db_api.get_task_executions(workflow_execution_id=wf_ex.id)

        self.assertTrue(len(tasks) >= 2)

        task1 = self._assert_single_item(tasks, name='task1')

        self.await_task_success(task1.id)

        # Once task1 is finished we know that join_task must be created.

        tasks = db_api.get_task_executions(workflow_execution_id=wf_ex.id)

        self._assert_single_item(
            tasks,
            name='join_task',
            state=states.WAITING
        )

        calls = db_api.get_delayed_calls()

        mtd_name = 'mistral.engine.task_handler._refresh_task_state'

        self._assert_single_item(calls, target_method_name=mtd_name)

        # Stop the workflow.
        db_api.delete_workflow_execution(wf_ex.id)

        self._await(
            lambda:
            len(db_api.get_delayed_calls(target_method_name=mtd_name)) == 0
        )
