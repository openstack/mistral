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

from oslo.config import cfg

from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import workflows as wf_service
from mistral.tests import base
from mistral import utils
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKFLOW_LIST = """
---
version: '2.0'

wf1:
  tags: [test, v2]
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

UPDATED_WORKFLOW_LIST = """
---
version: '2.0'

wf1:
  type: reverse
  input:
    - param1
    - param2
  output:
    result: "{$.result}"

  tasks:
    task1:
      action: std.echo output="{$.param1}{$.param2}"
      publish:
        result: "{$}"
"""


INVALID_WORKFLOW = """
---
verstion: '2.0'

wf:
  type: direct
  tasks:
    task1:
      action: std.echo output="Task 1"
"""


class WorkflowServiceTest(base.DbTestCase):
    def test_create_workflows(self):
        db_wfs = wf_service.create_workflows(WORKFLOW_LIST)

        self.assertEqual(2, len(db_wfs))

        # Workflow 1.
        wf1_db = self._assert_single_item(db_wfs, name='wf1')
        wf1_spec = spec_parser.get_workflow_spec(wf1_db.spec)

        self.assertEqual('wf1', wf1_spec.get_name())
        self.assertListEqual(['test', 'v2'], wf1_spec.get_tags())
        self.assertEqual('reverse', wf1_spec.get_type())

        # Workflow 2.
        wf2_db = self._assert_single_item(db_wfs, name='wf2')
        wf2_spec = spec_parser.get_workflow_spec(wf2_db.spec)

        self.assertEqual('wf2', wf2_spec.get_name())
        self.assertEqual('direct', wf2_spec.get_type())

    def test_update_workflows(self):
        db_wfs = wf_service.create_workflows(WORKFLOW_LIST)

        self.assertEqual(2, len(db_wfs))

        # Workflow 1.
        wf1_db = self._assert_single_item(db_wfs, name='wf1')
        wf1_spec = spec_parser.get_workflow_spec(wf1_db.spec)

        self.assertEqual('wf1', wf1_spec.get_name())
        self.assertEqual('reverse', wf1_spec.get_type())
        self.assertIn('param1', wf1_spec.get_input())
        self.assertIs(
            wf1_spec.get_input().get('param1'),
            utils.NotDefined
        )

        db_wfs = wf_service.update_workflows(UPDATED_WORKFLOW_LIST)

        self.assertEqual(1, len(db_wfs))

        wf1_db = self._assert_single_item(db_wfs, name='wf1')
        wf1_spec = spec_parser.get_workflow_spec(wf1_db.spec)

        self.assertEqual('wf1', wf1_spec.get_name())
        self.assertListEqual([], wf1_spec.get_tags())
        self.assertEqual('reverse', wf1_spec.get_type())
        self.assertIn('param1', wf1_spec.get_input())
        self.assertIn('param2', wf1_spec.get_input())
        self.assertIs(
            wf1_spec.get_input().get('param1'),
            utils.NotDefined
        )
        self.assertIs(
            wf1_spec.get_input().get('param2'),
            utils.NotDefined
        )

    def test_invalid_workflow_list(self):
        exception = self.assertRaises(
            exc.InvalidModelException,
            wf_service.create_workflows,
            INVALID_WORKFLOW
        )

        self.assertIn("Invalid DSL", exception.message)
