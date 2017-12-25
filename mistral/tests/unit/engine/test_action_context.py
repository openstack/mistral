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

import mock

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral_lib import actions as actions_base


WF = """
---
version: '2.0'

wf:
  tasks:
    task1:
      action: my_action
"""


class MyAction(actions_base.Action):

    def run(self, context):
        pass


class ActionContextTest(base.EngineTestCase):
    def setUp(self):
        super(ActionContextTest, self).setUp()

        test_base.register_action_class('my_action', MyAction)

    @mock.patch.object(MyAction, 'run', return_value=None)
    def test_context(self, mocked_run):
        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        self.assertEqual(1, len(mocked_run.call_args_list))
        action_context = mocked_run.call_args[0][0]
        exec_context = action_context.execution

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertEqual(exec_context.workflow_execution_id, wf_ex.id)

            tasks = wf_ex.task_executions
            task1 = self._assert_single_item(tasks, name='task1')
            a_ex = task1.action_executions[0]

            self.assertEqual(exec_context.task_id, task1.id)

            self.assertEqual(exec_context.workflow_name, wf_ex.name)

            callback_url = "/v2/action_executions/{}".format(a_ex.id)

            self.assertEqual(exec_context.callback_url, callback_url)
            self.assertEqual(exec_context.action_execution_id, a_ex.id)
