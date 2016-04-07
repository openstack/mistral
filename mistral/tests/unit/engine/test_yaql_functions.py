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
from mistral.tests.unit.engine import base as engine_test_base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class YAQLFunctionsEngineTest(engine_test_base.EngineTestCase):
    def test_task_function(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              description: This is task 1
              tags: ['t1']
              action: std.echo output=1
              publish:
                name: <% task(task1).name %>
                description: <% task(task1).spec.description %>
                tags: <% task(task1).spec.tags%>
                state: <% task(task1).state %>
                state_info: <% task(task1).state_info %>
                res: <% task(task1).result %>
              on-success:
                - task2

            task2:
              action: std.echo output=<% task(task1).result + 1 %>
              publish:
                name: <% task(task1).name %>
                description: <% task(task1).spec.description %>
                tags: <% task(task1).spec.tags%>
                state: <% task(task1).state %>
                state_info: <% task(task1).state_info %>
                res: <% task(task1).result %>
                task2_res: <% task(task2).result %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_execution_success(wf_ex.id)

        # Reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)

        tasks = wf_ex.task_executions

        task1 = self._assert_single_item(
            tasks,
            name='task1',
            state=states.SUCCESS
        )
        task2 = self._assert_single_item(
            tasks,
            name='task2',
            state=states.SUCCESS
        )

        self.assertDictEqual(
            {
                'name': 'task1',
                'description': 'This is task 1',
                'tags': ['t1'],
                'state': states.SUCCESS,
                'state_info': None,
                'res': 1
            },
            task1.published
        )
        self.assertDictEqual(
            {
                'name': 'task1',
                'description': 'This is task 1',
                'tags': ['t1'],
                'state': states.SUCCESS,
                'state_info': None,
                'res': 1,
                'task2_res': 2
            },
            task2.published
        )

    def test_task_function_non_existing(self):
        wf_text = """---
            version: '2.0'

            wf:
              type: direct
              output:
                task_name: <% task(non_existing_task).name %>

              tasks:
                task1:
                  action: std.noop
            """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf', {})

        self.await_execution_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('non_existing_task', wf_ex.state_info)
