# Copyright 2015 - Mirantis, Inc.
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


from mistral.db.v2.sqlalchemy import models
from mistral.tests.unit import base
from mistral.workflow import states
from mistral.workflow import with_items


class WithItemsTest(base.BaseTest):
    @staticmethod
    def get_action_ex(accepted, state, index):
        return models.ActionExecution(
            accepted=accepted,
            state=state,
            runtime_context={'index': index}
        )

    def test_get_indices(self):
        # Task execution for running 6 items with concurrency=3.
        task_ex = models.TaskExecution(
            spec={
                'action': 'myaction'
            },
            runtime_context={
                'with_items_context': {
                    'capacity': 3,
                    'count': 6
                }
            },
            action_executions=[],
            workflow_executions=[]
        )

        # Set 3 items: 2 success and 1 error unaccepted.
        task_ex.action_executions += [
            self.get_action_ex(True, states.SUCCESS, 0),
            self.get_action_ex(True, states.SUCCESS, 1),
            self.get_action_ex(False, states.ERROR, 2)
        ]

        # Then call get_indices and expect [2, 3, 4].
        indices = with_items.get_indices_for_loop(task_ex)

        # TODO(rakhmerov): Restore concurrency support.
        # With disabled 'concurrency' support we expect indices 2,3,4,5
        # because overall count is 6 and two indices were already processed.
        self.assertListEqual([2, 3, 4, 5], indices)
