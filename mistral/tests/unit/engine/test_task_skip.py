# Copyright 2022 - NetCracker Technology Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service

from mistral.tests.unit.engine import base
from mistral.workflow import states


class TaskSkipTest(base.EngineTestCase):

    def test_basic_task_skip(self):
        workflow = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.fail
              on-skip: t2
              on-success: t3
            t2:
              action: std.noop
            t3:
              action: std.noop
        """
        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        # Check that on-skip branch was not executed
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))
        t1_ex = self._assert_single_item(
            task_execs,
            name='t1',
            state=states.ERROR
        )

        # Skip t1 and wait for wf to complete
        self.engine.rerun_workflow(t1_ex.id, skip=True)
        self.await_workflow_success(wf_ex.id)

        # Check that on-skip branch was executed
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))
        self._assert_single_item(task_execs, name='t1', state=states.SKIPPED)
        self._assert_single_item(task_execs, name='t2', state=states.SUCCESS)

    def test_task_skip_on_workflow_tail(self):
        workflow = """
        version: '2.0'
        wf:
          tasks:
            t0:
              action: std.noop
              on-success: t1
            t1:
              action: std.fail
        """
        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        # Check that on-skip branch was not executed
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))
        t1_ex = self._assert_single_item(
            task_execs,
            name='t1',
            state=states.ERROR
        )

        # Skip t1 and wait for wf to complete
        self.engine.rerun_workflow(t1_ex.id, skip=True)
        self.await_workflow_success(wf_ex.id)

        # Check that on-skip branch was executed
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))
        self._assert_single_item(task_execs, name='t0', state=states.SUCCESS)
        self._assert_single_item(task_execs, name='t1', state=states.SKIPPED)

    def test_skip_subworkflow(self):
        workflow = """
        version: '2.0'
        wf:
          tasks:
            t0:
              action: std.noop
              on-success: t1
            t1:
              workflow: subwf
        subwf:
          tasks:
            t0:
              action: std.fail
        """
        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        # Check that on-skip branch was not executed
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))
        t1_ex = self._assert_single_item(
            task_execs,
            name='t1',
            state=states.ERROR
        )

        # Skip t1 and wait for wf to complete
        self.engine.rerun_workflow(t1_ex.id, skip=True)
        self.await_workflow_success(wf_ex.id)

        # Check that on-skip branch was executed
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(2, len(task_execs))
        self._assert_single_item(task_execs, name='t0', state=states.SUCCESS)
        self._assert_single_item(task_execs, name='t1', state=states.SKIPPED)

    def test_publish_on_skip(self):
        workflow = """
        version: '2.0'
        wf:
          tasks:
            t0:
              action: std.noop
              on-success: t1
            t1:
              action: std.fail
              publish:
                success: 1
              publish-on-error:
                error: 1
              publish-on-skip:
                skip: 1
        """
        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

            self.assertEqual(states.ERROR, wf_ex.state)
            self.assertEqual(2, len(task_execs))

            t1_ex = self._assert_single_item(
                task_execs,
                name='t1',
                state=states.ERROR
            )

            publish_before_skip = {"error": 1}
            self.assertDictEqual(publish_before_skip, t1_ex.published)

        # Skip t1 and wait for wf to complete
        self.engine.rerun_workflow(t1_ex.id, skip=True)
        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

            t1_ex = self._assert_single_item(
                task_execs,
                name='t1',
                state=states.SKIPPED
            )

            publish_after_skip = {"skip": 1}
            self.assertDictEqual(publish_after_skip, t1_ex.published)
            self.assertDictEqual(publish_after_skip, wf_ex.output)

    def test_retry_dont_conflict_with_skip(self):
        workflow = """
        version: '2.0'
        wf:
          tasks:
            t1:
              action: std.fail
              on-skip: skip
              retry:
                count: 2
                delay: 0
            skip:
              action: std.noop
        """
        wf_service.create_workflows(workflow)

        wf_ex = self.engine.start_workflow('wf')
        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

        t1_ex = self._assert_single_item(
            task_execs,
            name='t1',
            state=states.ERROR
        )

        self.engine.rerun_workflow(t1_ex.id, skip=True)
        self.await_workflow_success(wf_ex.id)
