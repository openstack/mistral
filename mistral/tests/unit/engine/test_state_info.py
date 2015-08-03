# Copyright 2014 - Mirantis, Inc.
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

from oslo_config import cfg
from oslo_log import log as logging

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base

LOG = logging.getLogger(__name__)
# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class ExecutionStateInfoTest(base.EngineTestCase):
    def test_state_info(self):
        workflow = """---
        version: '2.0'
        test_wf:
          type: direct
          tasks:
            task1:
              action: std.fail

            task2:
              action: std.noop
        """
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_wf', {})

        self._await(lambda: self.is_execution_error(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn("error in task 'task1'", wf_ex.state_info)

    def test_state_info_two_failed_branches(self):
        workflow = """---
        version: '2.0'
        test_wf:
          type: direct
          tasks:
            task1:
              action: std.fail

            task2:
              action: std.fail
        """
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_wf', {})

        self._await(lambda: self.is_execution_error(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn("error in task 'task1'", wf_ex.state_info)
        self.assertIn("error in task 'task2'", wf_ex.state_info)

    def test_state_info_with_policies(self):
        workflow = """---
        version: '2.0'
        test_wf:
          type: direct
          tasks:
            task1:
              action: std.fail
              wait-after: 1

            task2:
              action: std.noop
              wait-after: 3
        """
        wf_service.create_workflows(workflow)

        # Start workflow.
        wf_ex = self.engine.start_workflow('test_wf', {})

        self._await(lambda: self.is_execution_error(wf_ex.id))

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn("error in task 'task1'", wf_ex.state_info)
