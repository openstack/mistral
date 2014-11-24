# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import copy

from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine import states
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base

# TODO(nmakhotkin) Need to write more tests.

LOG = logging.getLogger(__name__)
# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WORKBOOK = """
---
version: "2.0"

name: wb1

workflows:
  for_each:
    type: direct

    input:
     - names_info

    tasks:
      task1:
        for-each:
          name_info: $.names_info
        action: std.echo output={$.name_info.name}
        publish:
          result: $

"""

WORKBOOK_WITH_STATIC_VAR = """
---
version: "2.0"

name: wb1

workflows:
  for_each:
    type: direct

    input:
     - names_info
     - greeting

    tasks:
      task1:
        for-each:
          name_info: $.names_info
        action: std.echo output="{$.greeting}, {$.name_info.name}!"
        publish:
          result: $
"""


WORKFLOW_INPUT = {
    'names_info': [
        {'name': 'John'},
        {'name': 'Ivan'},
        {'name': 'Mistral'}
    ]
}


class ForEachEngineTest(base.EngineTestCase):
    def test_for_each_simple(self):
        wb_service.create_workbook_v2(WORKBOOK)

        # Start workflow.
        exec_db = self.engine.start_workflow('wb1.for_each', WORKFLOW_INPUT)

        self._await(
            lambda: self.is_execution_success(exec_db.id),
        )

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        tasks = exec_db.tasks
        task1 = self._assert_single_item(tasks, name='task1')

        # Since we know that we can receive results in random order,
        # check is not depend on order of items.
        result = task1.output['result']
        self.assertTrue(isinstance(result, list))

        self.assertIn('John', result)
        self.assertIn('Ivan', result)
        self.assertIn('Mistral', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)

    def test_for_each_static_var(self):
        wb_service.create_workbook_v2(WORKBOOK_WITH_STATIC_VAR)

        wf_input = copy.copy(WORKFLOW_INPUT)
        wf_input.update({'greeting': 'Hello'})
        # Start workflow.
        exec_db = self.engine.start_workflow('wb1.for_each', wf_input)

        self._await(
            lambda: self.is_execution_success(exec_db.id),
        )

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        tasks = exec_db.tasks
        task1 = self._assert_single_item(tasks, name='task1')
        result = task1.output['result']

        self.assertTrue(isinstance(result, list))

        self.assertIn('Hello, John!', result)
        self.assertIn('Hello, Ivan!', result)
        self.assertIn('Hello, Mistral!', result)

        self.assertEqual(1, len(tasks))
        self.assertEqual(states.SUCCESS, task1.state)
