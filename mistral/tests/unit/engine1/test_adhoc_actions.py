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

from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base

LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKBOOK = """
---
Version: '2.0'

Actions:
  my_action:
    base: std.echo
    base-parameters:
      output: "{$.str1}{$.str2}"
    output: "{$}{$}"

Workflows:
  wf1:
    type: direct
    start-task: task1
    parameters:
      - str1
      - str2
    output:
      result: $.result

    tasks:
      task1:
        action: my_action str1='{$.str1}' str2='{$.str2}'
        publish:
          result: $
"""


class AdhocActionsTest(base.EngineTestCase):
    def setUp(self):
        super(AdhocActionsTest, self).setUp()

        wb_service.create_workbook_v2({
            'name': 'my_wb',
            'definition': WORKBOOK,
            'tags': ['test']
        })

    def test_run_workflow_with_adhoc_action(self):
        exec_db = self.engine.start_workflow(
            'my_wb.wf1',
            {'str1': 'a', 'str2': 'b'}
        )

        self._await(lambda: self.is_execution_success(exec_db.id))

        exec_db = db_api.get_execution(exec_db.id)

        self.assertDictEqual({'result': 'abab'}, exec_db.output)
