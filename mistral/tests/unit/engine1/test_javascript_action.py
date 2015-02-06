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
from oslo.config import cfg
import testtools

from mistral.db.v2 import api as db_api
from mistral.engine import states
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base
from mistral.utils import javascript

LOG = logging.getLogger(__name__)
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
          script: f = 50 * 10; return f
          # Skip this '$' sign until bug
          # https://bugs.launchpad.net/mistral/+bug/1415886 is resolved.
          # return $['num'] * 10
          context: $

        publish:
          result: $.task1

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
        exec_db = self.engine.start_workflow('test_js.js_test', {'num': 50})

        self._await(lambda: self.is_execution_success(exec_db.id))

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.SUCCESS, task_db.state)
        self.assertDictEqual({}, task_db.runtime_context)

        self.assertEqual(500, task_db.output['num_10_times'])
        self.assertEqual(100, task_db.output['result'])

    @mock.patch.object(javascript, 'evaluate', fake_evaluate)
    def test_fake_javascript_action_data_context(self):
        wb_service.create_workbook_v2(WORKBOOK)

        # Start workflow.
        exec_db = self.engine.start_workflow('test_js.js_test', {'num': 50})

        self._await(lambda: self.is_execution_success(exec_db.id))

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(states.SUCCESS, task_db.state)
        self.assertDictEqual({}, task_db.runtime_context)

        self.assertEqual(500, task_db.output['result'])
