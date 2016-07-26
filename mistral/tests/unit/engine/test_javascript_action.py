# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
from oslo_config import cfg
import testtools

from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine import base
from mistral.utils import javascript
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
version: "2.0"

name: test_js

workflows:
  js_test:
    type: direct

    input:
      - num

    tasks:
      task1:
        description: |
          This task reads variable from context,
          increasing its value 10 times, writes result to context and
          returns 100 (expected result)
        action: std.javascript
        input:
          script: |
            return $['num'] * 10
          context: <% $ %>

        publish:
          result: <% task(task1).result %>

"""


def fake_evaluate(_, context):
    return context['num'] * 10


class JavaScriptEngineTest(base.EngineTestCase):
    def setUp(self):
        super(JavaScriptEngineTest, self).setUp()

    @testtools.skip('It requires installed JS engine.')
    def test_javascript_action(self):
        wb_service.create_workbook_v2(WORKBOOK)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_js.js_test', {'num': 50})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.assertEqual(500, task_ex.published['num_10_times'])
        self.assertEqual(100, task_ex.published['result'])

    @mock.patch.object(javascript, 'evaluate', fake_evaluate)
    def test_fake_javascript_action_data_context(self):
        wb_service.create_workbook_v2(WORKBOOK)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_js.js_test', {'num': 50})

        self.await_workflow_success(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)
        task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.assertEqual(500, task_ex.published['result'])
