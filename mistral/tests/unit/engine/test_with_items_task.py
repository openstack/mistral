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
from mistral.engine import tasks
from mistral.tests.unit import base
from mistral.workflow import states


# TODO(rakhmerov): This test is a legacy of the previous 'with-items'
# implementation when most of its logic was in with_items.py module.
# It makes sense to add more test for various methods of WithItemsTask.

class WithItemsTaskTest(base.BaseTest):
    @staticmethod
    def get_action_ex(accepted, state, index):
        return models.ActionExecution(
            accepted=accepted,
            state=state,
            runtime_context={'index': index}
        )

    def test_get_next_indices(self):
        # Task execution for running 6 items with concurrency=3.
        task_ex = models.TaskExecution(
            spec={
                'action': 'myaction'
            },
            runtime_context={
                'with_items': {
                    'capacity': 3,
                    'count': 6
                }
            },
            action_executions=[],
            workflow_executions=[]
        )

        task = tasks.WithItemsTask(None, None, None, {}, task_ex)

        # Set 3 items: 2 success and 1 error unaccepted.
        task_ex.action_executions += [
            self.get_action_ex(True, states.SUCCESS, 0),
            self.get_action_ex(True, states.SUCCESS, 1),
            self.get_action_ex(False, states.ERROR, 2)
        ]

        # Then call get_indices and expect [2, 3, 4].
        indexes = task._get_next_indexes()

        self.assertListEqual([2, 3, 4], indexes)
