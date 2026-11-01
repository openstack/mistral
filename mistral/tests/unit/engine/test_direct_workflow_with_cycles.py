# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
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
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import data_flow
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class DirectWorkflowWithCyclesTest(base.EngineTestCase):
    def test_simple_cycle(self):
        wf_text = """
        version: 2.0

        workflow_cycle_in_out_verify:
          input:
            - num_of_cycles

          output:
            abc: <% $.counter %>

          tasks:
            initialize:
              publish:
                counter: 0
              on-success:
                - increment

            increment:
              action: std.noop
              publish:
                counter: <% $.counter + 1 %>
              on-success:
                - increment: <% $.counter < $.num_of_cycles %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow(
            'workflow_cycle_in_out_verify', wf_input={"num_of_cycles": 21}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual({'abc': 21}, wf_ex.output)

            t_execs = wf_ex.task_executions

        # Expecting one execution for task1 and two executions
        # for task2 and task3 because of the cycle 'task2 <-> task3'.
        self._assert_single_item(t_execs, name='initialize')
        self._assert_multiple_items(t_execs, 21, name='increment')

        self.assertEqual(22, len(t_execs))

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertTrue(all(states.SUCCESS == t_ex.state for t_ex in t_execs))

    def test_complex_cycle(self):
        wf_text = """
        version: '2.0'

        wf:
          vars:
            cnt: 0

          output:
            cnt: <% $.cnt %>

          tasks:
            task1:
              on-complete:
                - task2

            task2:
              action: std.echo output=2
              publish:
                cnt: <% $.cnt + 1 %>
              on-success:
                - task3

            task3:
              action: std.echo output=3
              on-complete:
                - task4

            task4:
              action: std.echo output=4
              on-success:
                - task2: <% $.cnt < 2 %>
                - task5: <% $.cnt >= 2 %>

            task5:
              action: std.echo output=<% $.cnt %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual({'cnt': 2}, wf_ex.output)

            t_execs = wf_ex.task_executions

        # Expecting one execution for task1 and task5 and two executions
        # for task2, task3 and task4 because of the cycle
        # 'task2 -> task3 -> task4 -> task2'.
        self._assert_single_item(t_execs, name='task1')
        self._assert_multiple_items(t_execs, 2, name='task2')
        self._assert_multiple_items(t_execs, 2, name='task3')
        self._assert_multiple_items(t_execs, 2, name='task4')

        task5_ex = self._assert_single_item(t_execs, name='task5')

        self.assertEqual(8, len(t_execs))

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertTrue(all(states.SUCCESS == t_ex.state for t_ex in t_execs))

        with db_api.transaction():
            task5_ex = db_api.get_task_execution(task5_ex.id)

            self.assertEqual(2, data_flow.get_task_execution_result(task5_ex))

    def test_parallel_cycles(self):
        wf_text = """
        version: '2.0'

        wf:
          vars:
            cnt: 0

          output:
            cnt: <% $.cnt %>

          tasks:
            task1:
              on-complete:
                - task1_2
                - task2_2

            task1_2:
              action: std.echo output=2
              publish:
                cnt: <% $.cnt + 1 %>
              on-success:
                - task1_3

            task1_3:
              action: std.echo output=3
              on-success:
                - task1_2: <% $.cnt < 2 %>

            task2_2:
              action: std.echo output=2
              publish:
                cnt: <% $.cnt + 1 %>
              on-success:
                - task2_3

            task2_3:
              action: std.echo output=3
              on-success:
                - task2_2: <% $.cnt < 3 %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            wf_output = wf_ex.output
            t_execs = wf_ex.task_executions

        # NOTE: We have two cycles in parallel workflow branches
        # and those branches will have their own copy of "cnt" variable
        # so both cycles must complete correctly.
        self._assert_single_item(t_execs, name='task1')
        self._assert_multiple_items(t_execs, 2, name='task1_2')
        self._assert_multiple_items(t_execs, 2, name='task1_3')
        self._assert_multiple_items(t_execs, 3, name='task2_2')
        self._assert_multiple_items(t_execs, 3, name='task2_3')

        self.assertEqual(11, len(t_execs))

        self.assertEqual(states.SUCCESS, wf_ex.state)
        self.assertTrue(all(states.SUCCESS == t_ex.state for t_ex in t_execs))

        # TODO(rakhmerov): We have this uncertainty because of the known
        # bug: https://bugs.launchpad.net/mistral/liberty/+bug/1424461
        # Now workflow output is almost always 3 because the second cycle
        # takes longer hence it wins because of how DB queries work: they
        # order entities in ascending of creation time.
        self.assertTrue(wf_output['cnt'] == 2 or wf_output['cnt'] == 3)

    def _start_loop(self, num_of_cycles):
        wf_text = """
        version: 2.0

        wf:
          input:
            - num_of_cycles

          vars:
            counter: 0

          tasks:
            start:
              on-success:
                - increment

            increment:
              action: std.noop
              publish:
                counter: <% $.counter + 1 %>
              on-success:
                - increment: <% $.counter < $.num_of_cycles %>
        """

        wf_service.create_workflows(wf_text)

        return self.engine.start_workflow(
            'wf', wf_input={'num_of_cycles': num_of_cycles}
        )

    def test_max_task_executions_within_limit(self):
        self.override_config('max_task_executions', 5, 'engine')

        wf_ex = self._start_loop(5)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self._assert_multiple_items(
                wf_ex.task_executions, 5, name='increment'
            )

    def test_max_task_executions_exceeded(self):
        self.override_config('max_task_executions', 5, 'engine')

        wf_ex = self._start_loop(10)

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

        self.assertEqual(7, len(t_execs))

        failed = self._assert_single_item(t_execs, state=states.ERROR)

        expected = (
            "Task 'increment' ran too many times in this workflow "
            "execution [limit=5]"
        )

        self.assertEqual(expected, failed.state_info)
        self.assertEqual(expected, wf_ex.state_info)

        self._assert_multiple_items(
            t_execs, 5, name='increment', state=states.SUCCESS
        )

    def test_max_task_executions_infinite_loop(self):
        self.override_config('max_task_executions', 3, 'engine')

        wf_text = """
        version: 2.0

        wf:
          tasks:
            start:
              on-complete:
                - task1

            task1:
              action: std.fail
              on-complete:
                - task2

            task2:
              action: std.noop
              on-complete:
                - task1
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_execs = wf_ex.task_executions

        self.assertEqual(8, len(t_execs))
        self.assertIn("Task 'task1' ran too many times", wf_ex.state_info)

    def test_max_task_executions_unlimited(self):
        self.override_config('max_task_executions', 0, 'engine')

        wf_ex = self._start_loop(10)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self._assert_multiple_items(
                wf_ex.task_executions, 10, name='increment'
            )
