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

from unittest import mock

from oslo_config import cfg
from oslo_utils import importutils
import testtools

from mistral.db.v2 import api as db_api
from mistral.expressions import yaql_expression
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.utils import javascript
from mistral.workflow import states

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


JAVASCRIPT_WORKFLOW = """
version: "2.0"
wf:
  input:
    - length
  tasks:
    task1:
      action: std.javascript
      input:
        script: |
          let numberSequence = Array.from({length: $['length']},
                                          (x, i) => i);
          let evenNumbers = numberSequence.filter(x => x % 2 === 0);

          return evenNumbers.length;
        context: <% $ %>
      publish:
        res: <% task().result %>
"""


def fake_evaluate(_, context):
    return context['length'] / 2


class JavaScriptEngineTest(base.EngineTestCase):

    @testtools.skipIf(not importutils.try_import('py_mini_racer'),
                      'This test requires that py_mini_racer library was '
                      'installed')
    def test_py_mini_racer_javascript_action(self):
        cfg.CONF.set_default('js_implementation', 'py_mini_racer')

        length = 1000

        wf_service.create_workflows(JAVASCRIPT_WORKFLOW)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            wf_input={'length': length}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.assertEqual(length / 2, task_ex.published['res'])

    @testtools.skipIf(not importutils.try_import('py_mini_racer'),
                      'This test requires that py_mini_racer library was '
                      'installed')
    def test_py_mini_racer_javascript_action_disabled_yaql_conversion(self):
        cfg.CONF.set_default('js_implementation', 'py_mini_racer')

        # Both input and output data conversion in YAQL need to be disabled
        # so that we're sure that there won't be any surprises from YAQL
        # like some YAQL internal types included in expression results.
        self.override_config('convert_input_data', False, 'yaql')
        self.override_config('convert_output_data', False, 'yaql')

        # Setting YAQL engine to None so it reinitialized again with the
        # right values upon the next use.
        yaql_expression.YAQL_ENGINE = None

        wf_text = """---
        version: '2.0'

        wf:
          input:
            - param: default_val

          tasks:
            task1:
              action: std.js
              input:
                context: <% $ %>
                script: >
                  return $.param
              publish:
                result: <% task().result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

            self.assertDictEqual({'result': 'default_val'}, t_ex.published)

    @mock.patch.object(javascript, 'evaluate', fake_evaluate)
    def test_fake_javascript_action_data_context(self):
        length = 1000

        wf_service.create_workflows(JAVASCRIPT_WORKFLOW)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            wf_input={'length': length}
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)
            task_ex = wf_ex.task_executions[0]

        self.assertEqual(states.SUCCESS, task_ex.state)
        self.assertDictEqual({}, task_ex.runtime_context)

        self.assertEqual(length / 2, task_ex.published['res'])
