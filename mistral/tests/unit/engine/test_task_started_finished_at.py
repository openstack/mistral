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

from mistral.tests.unit.engine import base

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service

WF_FAIL_WITH_WAIT = """
version: "2.0"

wf_fail:
  tasks:
    task1:
      action: std.fail
      wait-before: 2
"""

WF_JOIN_ALL = """
version: "2.0"

wf_join:
  tasks:
    wait_2:
      action: std.sleep seconds=2
      on-success: finish_wf
    wait_4:
      action: std.sleep seconds=4
      on-success: finish_wf
    wait_6:
      action: std.sleep seconds=6
      on-success: finish_wf
    finish_wf:
      join: all
      action: std.sleep seconds=2
"""

WF_WITH_RETRIES = """
version: "2.0"

wf_retry:
  tasks:
    task1:
      action: std.fail
      retry:
        delay: 1
        count: 5
"""

WF_WAIT_BEFORE_AFTER = """
version: "2.0"

wf_wait:
  tasks:
    task1:
      action: std.noop
      wait-before: 3
      wait-after: 3
"""


class TaskStartedFinishedAtTest(base.EngineTestCase):

    def setUp(self):
        super(TaskStartedFinishedAtTest, self).setUp()

    def test_started_finished_fields_updated_after_rerun(self):
        wf_service.create_workflows(WF_FAIL_WITH_WAIT)
        wf_ex = self.engine.start_workflow('wf_fail')
        self.await_workflow_error(wf_ex.id)

        task_ex = self._get_task_from_wf(wf_ex.id)
        started_1st, finished_1st = self._get_started_finished(task_ex)

        wf_ex = self.engine.rerun_workflow(task_ex.id)

        task_ex = self._get_task_from_wf(wf_ex.id)
        self.assertIsNone(task_ex.finished_at)
        self.await_workflow_error(wf_ex.id)

        task_ex = self._get_task_from_wf(wf_ex.id)
        started_2nd, finished_2nd = self._get_started_finished(task_ex)

        self.assertNotEqual(started_1st, started_2nd)
        self.assertNotEqual(finished_1st, finished_2nd)

    def test_correct_duration_in_case_of_join_all(self):
        wf_service.create_workflows(WF_JOIN_ALL)
        wf_ex = self.engine.start_workflow('wf_join')
        self.await_workflow_success(wf_ex.id)

        wait_2 = self._get_task_from_wf(wf_ex.id, 'wait_2')
        wait_4 = self._get_task_from_wf(wf_ex.id, 'wait_4')
        wait_6 = self._get_task_from_wf(wf_ex.id, 'wait_6')
        finish_wf = self._get_task_from_wf(wf_ex.id, 'finish_wf')

        self._check_was_started_after(finish_wf, wait_2)
        self._check_was_started_after(finish_wf, wait_4)
        self._check_was_started_after(finish_wf, wait_6)

    def test_retries_do_not_update_created_at(self):
        wf_service.create_workflows(WF_WITH_RETRIES)
        wf_ex = self.engine.start_workflow('wf_retry')
        self.await_workflow_error(wf_ex.id)

        task_ex = self._get_task_from_wf(wf_ex.id)
        created_at = task_ex.created_at
        started_at = self._get_started_finished(task_ex)[0]

        self.assertEqual(created_at, started_at)

    def test_wait_before_after_are_included_to_duration(self):
        wf_service.create_workflows(WF_WAIT_BEFORE_AFTER)
        wf_ex = self.engine.start_workflow('wf_wait')
        self.await_workflow_success(wf_ex.id)

        task_ex = self._get_task_from_wf(wf_ex.id)
        started, finished = self._get_started_finished(task_ex)
        duration = self._get_task_duration(started, finished)

        self._check_duration_more_than(duration, 1)

    def _get_task_from_wf(self, wf_ex_id, name='task1'):
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex_id)
            task_execs = wf_ex.task_executions
        return self._assert_single_item(task_execs, name=name)

    def _get_started_finished(self, task_ex):
        started_at = task_ex.started_at
        finished_at = task_ex.finished_at
        self.assertIsNotNone(started_at)
        self.assertIsNotNone(finished_at)
        return started_at, finished_at

    def _get_task_duration(self, start_time, finish_time):
        return (finish_time - start_time).total_seconds()

    def _check_was_started_after(self, task_started, task_finished):
        first_finished = self._get_started_finished(task_finished)[1]
        second_started = self._get_started_finished(task_started)[0]
        delta = self._get_task_duration(first_finished, second_started)

        self.assertTrue(
            delta >= 0,
            "Expected {} was started after {} was finished".format(
                task_started.name, task_finished.name)
        )

    def _check_duration_more_than(self, duration, time):
        self.assertTrue(
            time < duration,
            "Expected duration {} was more than {}".format(duration, time)
        )
