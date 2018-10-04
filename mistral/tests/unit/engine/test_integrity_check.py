# Copyright 2016 - Nokia Networks.
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

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


class IntegrityCheckTest(base.EngineTestCase):
    def setUp(self):
        super(IntegrityCheckTest, self).setUp()

        self.override_config('auth_enable', False, group='pecan')
        self.override_config(
            'execution_integrity_check_delay',
            2,
            group='engine'
        )

    def test_task_execution_integrity(self):
        self.override_config('execution_integrity_check_delay', 1, 'engine')

        # The idea of the test is that we use the no-op asynchronous action
        # so that action and task execution state is not automatically set
        # to SUCCESS after we start the workflow. We'll update the action
        # execution state to SUCCESS directly through the DB and will wait
        # till task execution integrity is checked and fixed automatically
        # by a periodic job after about 2 seconds.
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              on-success: task2

            task2:
              action: std.async_noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

        self.await_task_success(task1_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task2_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task2',
                state=states.RUNNING
            )
            action2_ex = self._assert_single_item(
                task2_ex.executions,
                state=states.RUNNING
            )

        db_api.update_action_execution(
            action2_ex.id,
            {'state': states.SUCCESS}
        )

        self.await_task_success(task2_ex.id)
        self.await_workflow_success(wf_ex.id)
