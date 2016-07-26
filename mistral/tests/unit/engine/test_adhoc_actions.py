# Copyright 2014 - Mirantis, Inc.
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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
version: '2.0'

name: my_wb

actions:
  concat_twice:
    base: std.echo
    base-input:
      output: "<% $.s1 %>+<% $.s2 %>"
    input:
      - s1: "a"
      - s2
    output: "<% $ %> and <% $ %>"

workflows:
  wf1:
    type: direct
    input:
      - str1
      - str2
    output:
      workflow_result: <% $.result %> # Access to execution context variables
      concat_task_result: <% task(concat).result %> # Same but via task name

    tasks:
      concat:
        action: concat_twice s1=<% $.str1 %> s2=<% $.str2 %>
        publish:
          result: <% task(concat).result %>

  wf2:
    type: direct
    input:
      - str1
      - str2
    output:
      workflow_result: <% $.result %> # Access to execution context variables
      concat_task_result: <% task(concat).result %> # Same but via task name

    tasks:
      concat:
        action: concat_twice s2=<% $.str2 %>
        publish:
          result: <% task(concat).result %>

  wf3:
    type: direct
    input:
      - str1
      - str2

    tasks:
      concat:
        action: concat_twice
"""


class AdhocActionsTest(base.EngineTestCase):
    def setUp(self):
        super(AdhocActionsTest, self).setUp()

        wb_service.create_workbook_v2(WORKBOOK)

    def test_run_workflow_with_adhoc_action(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf1',
            {'str1': 'a', 'str2': 'b'}
        )

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.maxDiff = None

        self.assertDictEqual(
            {
                'workflow_result': 'a+b and a+b',
                'concat_task_result': 'a+b and a+b'
            },
            wf_ex.output
        )

    def test_run_adhoc_action_without_input_value(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf2',
            {'str1': 'a', 'str2': 'b'}
        )

        self.await_workflow_success(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.maxDiff = None

        self.assertDictEqual(
            {
                'workflow_result': 'a+b and a+b',
                'concat_task_result': 'a+b and a+b'
            },
            wf_ex.output
        )

    def test_run_adhoc_action_without_sufficient_input_value(self):
        wf_ex = self.engine.start_workflow(
            'my_wb.wf3',
            {'str1': 'a', 'str2': 'b'}
        )

        self.assertIn("Invalid input", wf_ex.state_info)
        self.assertEqual(states.ERROR, wf_ex.state)
