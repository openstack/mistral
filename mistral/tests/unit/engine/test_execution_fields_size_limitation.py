# Copyright 2015 - Mirantis, Inc.
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

from oslo_config import cfg

from mistral.actions import base as actions_base
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral.workflow import states
from mistral.workflow import utils as wf_utils


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WF = """
---
version: '2.0'

wf:
  input:
    - workflow_input: '__WORKFLOW_INPUT__'
    - action_output_length: 0

  tasks:
    task1:
      action: my_action
      input:
        action_input: '__ACTION_INPUT__'
        action_output_length: <% $.action_output_length %>
      publish:
        p_var: '__TASK_PUBLISHED__'
"""


class MyAction(actions_base.Action):
    def __init__(self, action_input, action_output_length):
        self.action_input = action_input
        self.action_output_length = action_output_length

    def run(self):
        return wf_utils.Result(
            data=''.join('A' for _ in range(self.action_output_length))
        )

    def test(self):
        raise NotImplementedError


def generate_workflow(tokens):
    new_wf = WF
    long_string = ''.join('A' for _ in range(1024))

    for token in tokens:
        new_wf = new_wf.replace(token, long_string)

    return new_wf


class ExecutionFieldsSizeLimitTest(base.EngineTestCase):
    def setUp(self):
        """Resets the size limit config between tests"""
        super(ExecutionFieldsSizeLimitTest, self).setUp()

        cfg.CONF.set_default(
            'execution_field_size_limit_kb',
            0,
            group='engine'
        )

        test_base.register_action_class('my_action', MyAction)

    def tearDown(self):
        """Restores the size limit config to default"""
        super(ExecutionFieldsSizeLimitTest, self).tearDown()

        cfg.CONF.set_default(
            'execution_field_size_limit_kb',
            1024,
            group='engine'
        )

    def test_default_limit(self):
        cfg.CONF.set_default(
            'execution_field_size_limit_kb',
            -1,
            group='engine'
        )

        new_wf = generate_workflow(
            ['__ACTION_INPUT_', '__WORKFLOW_INPUT__', '__TASK_PUBLISHED__']
        )

        wf_service.create_workflows(new_wf)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_success(wf_ex.id)

    def test_workflow_input_default_value_limit(self):
        new_wf = generate_workflow(['__WORKFLOW_INPUT__'])

        wf_service.create_workflows(new_wf)

        # Start workflow.
        e = self.assertRaises(
            exc.SizeLimitExceededException,
            self.engine.start_workflow,
            'wf',
            {}
        )

        self.assertEqual(
            "Size of 'input' is 1KB which exceeds the limit of 0KB",
            e.message
        )

    def test_workflow_input_limit(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        e = self.assertRaises(
            exc.SizeLimitExceededException,
            self.engine.start_workflow,
            'wf',
            {'workflow_input': ''.join('A' for _ in range(1024))}
        )

        self.assertEqual(
            "Size of 'input' is 1KB which exceeds the limit of 0KB",
            e.message
        )

    def test_action_input_limit(self):
        new_wf = generate_workflow(['__ACTION_INPUT__'])

        wf_service.create_workflows(new_wf)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn(
            "Size of 'input' is 1KB which exceeds the limit of 0KB",
            wf_ex.state_info
        )

    def test_action_output_limit(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            {'action_output_length': 1024}
        )

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn(
            "Size of 'output' is 1KB which exceeds the limit of 0KB",
            wf_ex.state_info
        )
        self.assertEqual(states.ERROR, wf_ex.state)

    def test_task_published_limit(self):
        new_wf = generate_workflow(['__TASK_PUBLISHED__'])

        wf_service.create_workflows(new_wf)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf', {})

        self.await_workflow_error(wf_ex.id)

        # Note: We need to reread execution to access related tasks.
        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertIn(
            'Failed to handle action completion [wf=wf, task=task1',
            wf_ex.state_info
        )

        task_ex = self._assert_single_item(wf_ex.task_executions, name='task1')

        self.assertIn(
            "Size of 'published' is 1KB which exceeds the limit of 0KB",
            task_ex.state_info
        )

    def test_workflow_params_limit(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        long_string = ''.join('A' for _ in range(1024))

        e = self.assertRaises(
            exc.SizeLimitExceededException,
            self.engine.start_workflow,
            'wf',
            {},
            '',
            env={'param': long_string}
        )

        self.assertIn(
            "Size of 'params' is 1KB which exceeds the limit of 0KB",
            e.message
        )
