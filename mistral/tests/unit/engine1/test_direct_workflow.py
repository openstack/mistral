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

import mock
from oslo.config import cfg
from yaql import exceptions as yaql_exc

from mistral.db.v2 import api as db_api
from mistral.engine1 import default_engine as de
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine1 import base
from mistral.workflow import states

# TODO(nmakhotkin) Need to write more tests.

LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class DirectWorkflowEngineTest(base.EngineTestCase):

    def _run_workflow(self, worklfow_yaml):
        wf_service.create_workflows(worklfow_yaml)
        exec_db = self.engine.start_workflow('wf', {})
        self._await(lambda: self.is_execution_error(exec_db.id))

        return db_api.get_execution(exec_db.id)

    def test_direct_workflow_on_closures(self):
        WORKFLOW = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              description: That should lead to workflow fail.
              action: std.echo output="Echo"
              on-success:
                - task2
                - succeed
              on-complete:
                - task3
                - task4
                - fail
                - never_gets_here

            task2:
              action: std.echo output="Morpheus"

            task3:
              action: std.echo output="output"

            task4:
              action: std.echo output="output"

            never_gets_here:
              action: std.noop
        """
        exec_db = self._run_workflow(WORKFLOW)

        tasks = exec_db.tasks
        task1 = self._assert_single_item(tasks, name='task1')
        task3 = self._assert_single_item(tasks, name='task3')
        task4 = self._assert_single_item(tasks, name='task4')

        self.assertEqual(3, len(tasks))

        self._await(lambda: self.is_task_success(task1.id))
        self._await(lambda: self.is_task_success(task3.id))
        self._await(lambda: self.is_task_success(task4.id))

        self.assertTrue(exec_db.state, states.ERROR)

    def test_wrong_task_input(self):
        WORKFLOW_WRONG_TASK_INPUT = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2
            task2:
              description: Wrong task output should lead to workflow failure
              action: std.echo wrong_input="Hahaha"
        """
        exec_db = exec_db = self._run_workflow(WORKFLOW_WRONG_TASK_INPUT)
        task_db2 = exec_db.tasks[1]

        self.assertIn(
            "Failed to initialize action",
            task_db2.output['task'][task_db2.name]
        )
        self.assertIn(
            "unexpected keyword argument",
            task_db2.output['task'][task_db2.name]
        )

        self.assertTrue(exec_db.state, states.ERROR)
        self.assertIn(task_db2.output['error'], exec_db.state_info)

    def test_wrong_first_task_input(self):
        WORKFLOW_WRONG_FIRST_TASK_INPUT = """
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              action: std.echo wrong_input="Ha-ha"
        """
        exec_db = self._run_workflow(WORKFLOW_WRONG_FIRST_TASK_INPUT)
        task_db = exec_db.tasks[0]

        self.assertIn(
            "Failed to initialize action",
            task_db.output['task'][task_db.name]
        )
        self.assertIn(
            "unexpected keyword argument",
            task_db.output['task'][task_db.name]
        )

        self.assertTrue(exec_db.state, states.ERROR)
        self.assertIn(task_db.output['error'], exec_db.state_info)

    def test_wrong_action(self):
        WORKFLOW_WRONG_ACTION = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Echo"
              on-complete:
                - task2

            task2:
              action: action.doesnt_exist
        """
        exec_db = self._run_workflow(WORKFLOW_WRONG_ACTION)

        # TODO(dzimine): Catch tasks caused error, and set them to ERROR:
        # TODO(dzimine): self.assertTrue(task_db.state, states.ERROR)

        self.assertTrue(exec_db.state, states.ERROR)
        self.assertIn("Failed to find action", exec_db.state_info)

    def test_wrong_action_first_task(self):
        WORKFLOW_WRONG_ACTION_FIRST_TASK = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: wrong.task
        """
        wf_service.create_workflows(WORKFLOW_WRONG_ACTION_FIRST_TASK)
        with mock.patch.object(de.DefaultEngine, '_fail_workflow') as mock_fw:
            self.assertRaises(
                exc.InvalidActionException,
                self.engine.start_workflow, 'wf', None)

            mock_fw.assert_called_once()
            self.assertTrue(
                issubclass(
                    type(mock_fw.call_args[0][1]),
                    exc.InvalidActionException
                ),
                "Called with a right exception"
            )

    def test_messed_yaql(self):
        WORKFLOW_MESSED_YAQL = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Echo"
              # publish: {wrong yaql}
              on-complete:
                - task2

            task2:
              action: std.echo output="{wrong yaql}"
        """
        exec_db = self._run_workflow(WORKFLOW_MESSED_YAQL)

        self.assertTrue(exec_db.state, states.ERROR)

    def test_messed_yaql_in_first_task(self):
        WORKFLOW_MESSED_YAQL_IN_FIRST_TASK = """
        version: '2.0'

        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="{wrong(yaql)}"
        """
        wf_service.create_workflows(WORKFLOW_MESSED_YAQL_IN_FIRST_TASK)

        with mock.patch.object(de.DefaultEngine, '_fail_workflow') as mock_fw:
            self.assertRaises(
                yaql_exc.YaqlException, self.engine.start_workflow, 'wf', None)

            mock_fw.assert_called_once()
            self.assertTrue(
                issubclass(
                    type(mock_fw.call_args[0][1]),
                    yaql_exc.YaqlException
                ),
                "Called with a right exception"
            )
