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
from mistral.tests.unit import base
from mistral.workbook import parser as spec_parser


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
version: '2.0'

name: my_wb
tags: [test]

actions:
  concat:
    base: std.echo
    base-input:
      output: "{$.str1}{$.str2}"

workflows:
  wf1:
#Sample Comment 1
    type: reverse
    tags: [wf_test]
    input:
      - param1
    output:
      result: "{$.result}"

    tasks:
      task1:
        action: std.echo output="{$.param1}"
        publish:
          result: "{$}"

  wf2:
    type: direct
    output:
      result: "{$.result}"

    tasks:
      task1:
        workflow: my_wb.wf1 param1='Hi' task_name='task1'
        publish:
          result: "The result of subworkflow is '{$.final_result}'"
"""

WORKBOOK_WF1_DEFINITION = """wf1:
#Sample Comment 1
  type: reverse
  tags: [wf_test]
  input:
    - param1
  output:
    result: "{$.result}"

  tasks:
    task1:
      action: std.echo output="{$.param1}"
      publish:
        result: "{$}"
"""

WORKBOOK_WF2_DEFINITION = """wf2:
  type: direct
  output:
    result: "{$.result}"

  tasks:
    task1:
      workflow: my_wb.wf1 param1='Hi' task_name='task1'
      publish:
        result: "The result of subworkflow is '{$.final_result}'"
"""


UPDATED_WORKBOOK = """
---
version: '2.0'

name: my_wb
tags: [test]

actions:
  concat:
    base: std.echo
    base-input:
      output: "{$.str1}{$.str2}"

workflows:
  wf1:
    type: direct
    output:
      result: "{$.result}"

    tasks:
      task1:
        workflow: my_wb.wf2 param1='Hi' task_name='task1'
        publish:
          result: "The result of subworkflow is '{$.final_result}'"

  wf2:
    type: reverse
    input:
      - param1
    output:
      result: "{$.result}"

    tasks:
      task1:
        action: std.echo output="{$.param1}"
        publish:
          result: "{$}"
"""

UPDATED_WORKBOOK_WF1_DEFINITION = """wf1:
  type: direct
  output:
    result: "{$.result}"

  tasks:
    task1:
      workflow: my_wb.wf2 param1='Hi' task_name='task1'
      publish:
        result: "The result of subworkflow is '{$.final_result}'"
"""

UPDATED_WORKBOOK_WF2_DEFINITION = """wf2:
  type: reverse
  input:
    - param1
  output:
    result: "{$.result}"

  tasks:
    task1:
      action: std.echo output="{$.param1}"
      publish:
        result: "{$}"
"""


ACTION_DEFINITION = """concat:
  base: std.echo
  base-input:
    output: "{$.str1}{$.str2}"
"""


class WorkbookServiceTest(base.DbTestCase):
    def test_create_workbook(self):
        wb_db = wb_service.create_workbook_v2(WORKBOOK)

        self.assertIsNotNone(wb_db)
        self.assertEqual('my_wb', wb_db.name)
        self.assertEqual(WORKBOOK, wb_db.definition)
        self.assertIsNotNone(wb_db.spec)
        self.assertListEqual(['test'], wb_db.tags)

        db_actions = db_api.get_action_definitions(name='my_wb.concat')

        self.assertEqual(1, len(db_actions))

        # Action.
        action_db = self._assert_single_item(db_actions, name='my_wb.concat')

        self.assertFalse(action_db.is_system)

        action_spec = spec_parser.get_action_spec(action_db.spec)

        self.assertEqual('concat', action_spec.get_name())
        self.assertEqual('std.echo', action_spec.get_base())
        self.assertEqual(ACTION_DEFINITION, action_db.definition)

        db_wfs = db_api.get_workflow_definitions()

        self.assertEqual(2, len(db_wfs))

        # Workflow 1.
        wf1_db = self._assert_single_item(db_wfs, name='my_wb.wf1')
        wf1_spec = spec_parser.get_workflow_spec(wf1_db.spec)

        self.assertEqual('wf1', wf1_spec.get_name())
        self.assertEqual('reverse', wf1_spec.get_type())
        self.assertListEqual(['wf_test'], wf1_spec.get_tags())
        self.assertListEqual(['wf_test'], wf1_db.tags)
        self.assertEqual(WORKBOOK_WF1_DEFINITION, wf1_db.definition)

        # Workflow 2.
        wf2_db = self._assert_single_item(db_wfs, name='my_wb.wf2')
        wf2_spec = spec_parser.get_workflow_spec(wf2_db.spec)

        self.assertEqual('wf2', wf2_spec.get_name())
        self.assertEqual('direct', wf2_spec.get_type())
        self.assertEqual(WORKBOOK_WF2_DEFINITION, wf2_db.definition)

    def test_update_workbook(self):
        # Create workbook.
        wb_db = wb_service.create_workbook_v2(WORKBOOK)

        self.assertIsNotNone(wb_db)
        self.assertEqual(2, len(db_api.get_workflow_definitions()))

        # Update workbook.
        wb_db = wb_service.update_workbook_v2(UPDATED_WORKBOOK)

        self.assertIsNotNone(wb_db)
        self.assertEqual('my_wb', wb_db.name)
        self.assertEqual(UPDATED_WORKBOOK, wb_db.definition)
        self.assertListEqual(['test'], wb_db.tags)

        db_wfs = db_api.get_workflow_definitions()

        self.assertEqual(2, len(db_wfs))

        # Workflow 1.
        wf1_db = self._assert_single_item(db_wfs, name='my_wb.wf1')
        wf1_spec = spec_parser.get_workflow_spec(wf1_db.spec)

        self.assertEqual('wf1', wf1_spec.get_name())
        self.assertEqual('direct', wf1_spec.get_type())
        self.assertEqual(UPDATED_WORKBOOK_WF1_DEFINITION, wf1_db.definition)

        # Workflow 2.
        wf2_db = self._assert_single_item(db_wfs, name='my_wb.wf2')
        wf2_spec = spec_parser.get_workflow_spec(wf2_db.spec)

        self.assertEqual('wf2', wf2_spec.get_name())
        self.assertEqual('reverse', wf2_spec.get_type())
        self.assertEqual(UPDATED_WORKBOOK_WF2_DEFINITION, wf2_db.definition)
