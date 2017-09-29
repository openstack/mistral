# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
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
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class WorkflowVariablesTest(base.EngineTestCase):
    def test_workflow_variables(self):
        wf_text = """---
        version: '2.0'

        wf:
          input:
            - param1: "Hello"
            - param2

          vars:
            literal_var: "Literal value"
            yaql_var: "<% $.param1 %> <% $.param2 %>"

          output:
            literal_var: <% $.literal_var %>
            yaql_var: <% $.yaql_var %>

          tasks:
            task1:
              action: std.noop
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', '', {'param2': 'Renat'})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            wf_output = wf_ex.output
            tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(states.SUCCESS, task1.state)

        self.assertDictEqual(
            {
                'literal_var': 'Literal value',
                'yaql_var': 'Hello Renat'
            },
            wf_output
        )

    def test_dynamic_action_names(self):
        wf_text = """---
        version: '2.0'

        wf2:
          input:
            - wf_action
            - param1

          tasks:
            task1:
              action: <% $.wf_action %> output=<% $.param1 %>
              publish:
                var1: <% task(task1).result %>

        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf2',
            "",
            {"wf_action": "std.echo", "param1": "Hello"}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            wf_output = wf_ex.output
            tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual("Hello", wf_output['var1'])

    def test_dynamic_action_names_and_input(self):
        wf_text = """---
        version: '2.0'

        wf3:
          input:
            - wf_action
            - wf_input

          tasks:
            task1:
              action: <% $.wf_action %>
              input: <% $.wf_input %>
              publish:
                var1: <% task(task1).result %>

        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf3',
            "",
            {"wf_action": "std.echo", "wf_input": {"output": "Hello"}}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            wf_output = wf_ex.output
            tasks = wf_ex.task_executions

        task1 = self._assert_single_item(tasks, name='task1')

        self.assertEqual(states.SUCCESS, task1.state)
        self.assertEqual("Hello", wf_output['var1'])
