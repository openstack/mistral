# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest.mock import call
from unittest.mock import patch

from mistral.db.v2 import api as db_api
from mistral.engine import workflows
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states
from oslo_config import cfg

WORKFLOW = """
---
version: '2.0'
test_wf_1:
  tasks:
    t1:
      action: std.noop
    t2:
      action: std.noop
    t3:
      action: std.noop
    t4:
      action: std.noop
    t5:
      action: std.noop
"""


WORKFLOW_WITH_CHILD_WF = """
---
version: '2.0'
test_wf_2:
  tasks:
    t1:
      workflow: sub_workflow

sub_workflow:
  tasks:
    sub_wf_task:
      action: std.noop

"""


class WorkflowExecutionPlannedState(base.EngineTestCase):
    def setUp(self):
        super(WorkflowExecutionPlannedState, self).setUp()

    @patch.object(workflows.Workflow, '_notify')
    def test_workflow_execution_planned_is_set(self, mock_notify):
        cfg.CONF.set_default('start_workflow_as_planned', True, group='api')
        wf_service.create_workflows(WORKFLOW)
        wf_ex = self.engine.plan_workflow('test_wf_1')

        self.await_workflow_state(wf_ex.id, states.SUCCESS)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        mock_notify.assert_has_calls([
            call('PLANNED', 'RUNNING'),
            call('RUNNING', 'SUCCESS')
        ], any_order=False)

    @patch.object(workflows.Workflow, '_notify')
    def test_planned_for_childs_wf_ex_is_not_set(self, mock_notify):
        cfg.CONF.set_default('start_workflow_as_planned', True, group='api')
        wf_service.create_workflows(WORKFLOW_WITH_CHILD_WF)
        wf_ex = self.engine.plan_workflow('test_wf_2')

        self.await_workflow_state(wf_ex.id, states.SUCCESS)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.SUCCESS, wf_ex.state)
        mock_notify.assert_has_calls([
            call('PLANNED', 'RUNNING'),
            call('IDLE', 'RUNNING'),
            call('RUNNING', 'SUCCESS'),
            call('RUNNING', 'SUCCESS'),
        ], any_order=False)
