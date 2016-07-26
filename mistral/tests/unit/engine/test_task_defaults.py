# Copyright 2014 - Mirantis, Inc.
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

import datetime as dt
from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import scheduler
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class TaskDefaultsDirectWorkflowEngineTest(base.EngineTestCase):
    def test_task_defaults_on_error(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          task-defaults:
            on-error:
              - task3

          tasks:
            task1:
              description: That should lead to transition to task3.
              action: std.http url="http://some_url"
              on-success:
                - task2

            task2:
              action: std.echo output="Morpheus"

            task3:
              action: std.echo output="output"
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(2, len(tasks))
        self.assertEqual(states.ERROR, task1.state)
        self.assertEqual(states.SUCCESS, task3.state)


class TaskDefaultsReverseWorkflowEngineTest(base.EngineTestCase):
    def setUp(self):
        super(TaskDefaultsReverseWorkflowEngineTest, self).setUp()

        thread_group = scheduler.setup()

        self.addCleanup(thread_group.stop)

    def test_task_defaults_retry_policy(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: reverse

          task-defaults:
            retry:
              count: 2
              delay: 1

          tasks:
            task1:
              action: std.fail

            task2:
              action: std.echo output=2
              requires: [task1]
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {}, task_name='task2')

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(1, len(tasks))

        task1 = self._assert_single_item(
            tasks,
            name='task1',
            state=states.ERROR
        )

        self.assertTrue(
            task1.runtime_context['retry_task_policy']['retry_no'] > 0
        )

    def test_task_defaults_timeout_policy(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: reverse

          task-defaults:
            timeout: 1

          tasks:
            task1:
              action: std.async_noop

            task2:
              action: std.echo output=2
              requires: [task1]
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {}, task_name='task2')

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(1, len(tasks))

        self._assert_single_item(tasks, name='task1', state=states.ERROR)

        task_ex = db_api.get_task_execution(tasks[0].id)
        self.assertIn("Task timed out", task_ex.state_info)

    def test_task_defaults_wait_policies(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: reverse

          task-defaults:
            wait-before: 1
            wait-after: 1

          tasks:
            task1:
              action: std.echo output=1
        """

        wf_service.create_workflows(wf_text)

        time_before = dt.datetime.now()

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {}, task_name='task1')

        self.await_workflow_success(wf_ex.id)

        # Workflow must work at least 2 seconds (1+1).
        self.assertGreater(
            (dt.datetime.now() - time_before).total_seconds(),
            2
        )

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(1, len(tasks))

        self._assert_single_item(tasks, name='task1', state=states.SUCCESS)

    def test_task_defaults_requires(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: reverse

          task-defaults:
            requires: [always_do]

          tasks:
            task1:
              action: std.echo output=1

            task2:
              action: std.echo output=1
              requires: [task1]

            always_do:
              action: std.echo output="Do something"

        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {}, task_name='task2')

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        tasks = wf_ex.task_executions

        self.assertEqual(3, len(tasks))

        self._assert_single_item(tasks, name='task1', state=states.SUCCESS)
        self._assert_single_item(tasks, name='task2', state=states.SUCCESS)
        self._assert_single_item(tasks, name='always_do', state=states.SUCCESS)
