# Copyright 2014 - Mirantis, Inc.
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

from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine import states
from mistral.openstack.common import log as logging
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base

LOG = logging.getLogger(__name__)
# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WORKBOOK = """
---
version: '2.0'
name: wb
workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hi,"
        publish:
          hi: $
        on-success:
          - task2

      task2:
        action: std.echo output="Morpheus"
        publish:
          username: $
        on-success:
          - task3

      task3:
        action: std.echo output="{$.hi} {$.username}!"
        publish:
          result: $
"""


class DataFlowEngineTest(base.EngineTestCase):
    def test_trivial_dataflow(self):
        wb_service.create_workbook_v2({'definition': WORKBOOK})

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        self._await(
            lambda: self.is_execution_success(exec_db.id),
        )

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        self.assertEqual(states.SUCCESS, exec_db.state)

        tasks = exec_db.tasks
        task3 = self._assert_single_item(tasks, name='task3')

        self.assertEqual(states.SUCCESS, task3.state)

        self.assertDictEqual(
            {
                'task': {
                    'task3': {'result': 'Hi, Morpheus!'},
                },
                'result': 'Hi, Morpheus!',
            },
            task3.output
        )
