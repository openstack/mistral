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
version: '2.0'

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        description: That should lead to workflow fail.
        action: std.echo output="Echo"
        on-success:
          - task2
          - succeed
        on-complete:
          - task3
          - task4
          - fail

      task2:
        action: std.echo output="Morpheus"

      task3:
        action: std.echo output="output"

      task4:
        action: std.echo output="output"
"""


class DirectWorkflowEngineTest(base.EngineTestCase):
    def test_direct_workflow_on_closures(self):
        wb_service.create_workbook_v2({'definition': WORKBOOK})

        # Start workflow.
        exec_db = self.engine.start_workflow('wb.wf1', {})

        self._await(
            lambda: self.is_execution_error(exec_db.id)
        )

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)

        tasks = exec_db.tasks
        task3 = self._assert_single_item(tasks, name='task3')
        task4 = self._assert_single_item(tasks, name='task4')

        self.assertEqual(3, len(tasks))

        self._await(
            lambda: self.is_task_success(task3.id)
        )
        self._await(
            lambda: self.is_task_success(task4.id)
        )
