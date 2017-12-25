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

from mistral_lib import actions as actions_base

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.tests.unit import base as test_base
from mistral.tests.unit.engine import base
from mistral.workflow import states

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
    - action_output_dict: false
    - action_error: false

  tasks:
    task1:
      action: my_action
      input:
        input: '__ACTION_INPUT__'
        output_length: <% $.action_output_length %>
        output_dict: <% $.action_output_dict %>
        error: <% $.action_error %>
      publish:
        p_var: '__TASK_PUBLISHED__'
"""


class MyAction(actions_base.Action):
    def __init__(self, input, output_length, output_dict=False, error=False):
        self.input = input
        self.output_length = output_length
        self.output_dict = output_dict
        self.error = error

    def run(self, context):
        if not self.output_dict:
            result = ''.join('A' for _ in range(self.output_length))
        else:
            result = {}

            for i in range(self.output_length):
                result[i] = 'A'

        if not self.error:
            return actions_base.Result(data=result)
        else:
            return actions_base.Result(error=result)

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
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

    def test_workflow_input_default_value_limit(self):
        new_wf = generate_workflow(['__WORKFLOW_INPUT__'])

        wf_service.create_workflows(new_wf)

        # Start workflow.
        e = self.assertRaises(
            exc.SizeLimitExceededException,
            self.engine.start_workflow,
            'wf'
        )

        self.assertEqual(
            "Size of 'input' is 1KB which exceeds the limit of 0KB",
            str(e)
        )

    def test_workflow_input_limit(self):
        wf_service.create_workflows(WF)

        # Start workflow.
        e = self.assertRaises(
            exc.SizeLimitExceededException,
            self.engine.start_workflow,
            'wf',
            wf_input={'workflow_input': ''.join('A' for _ in range(1024))}
        )

        self.assertEqual(
            "Size of 'input' is 1KB which exceeds the limit of 0KB",
            str(e)
        )

    def test_action_input_limit(self):
        new_wf = generate_workflow(['__ACTION_INPUT__'])

        wf_service.create_workflows(new_wf)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

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
            wf_input={'action_output_length': 1024}
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
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        self.assertIn(
            'Failed to handle action completion [error=Size of',
            wf_ex.state_info
        )
        self.assertIn('wf=wf, task=task1', wf_ex.state_info)

        task_ex = self._assert_single_item(task_execs, name='task1')

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
            env={'param': long_string}
        )

        self.assertIn(
            "Size of 'params' is 1KB which exceeds the limit of 0KB",
            str(e)
        )

    def test_task_execution_state_info_trimmed(self):
        # No limit on output, input and other JSON fields.
        cfg.CONF.set_default(
            'execution_field_size_limit_kb',
            -1,
            group='engine'
        )

        wf_service.create_workflows(WF)

        # Start workflow.
        wf_ex = self.engine.start_workflow(
            'wf',
            wf_input={
                'action_output_length': 80000,
                'action_output_dict': True,
                'action_error': True
            }
        )

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = self._assert_single_item(
                wf_ex.task_executions,
                state=states.ERROR
            )

            # "state_info" must be trimmed so that it's not greater than 65535.
            self.assertLess(len(task_ex.state_info), 65536)
            self.assertGreater(len(task_ex.state_info), 65490)
            self.assertLess(len(wf_ex.state_info), 65536)
            self.assertGreater(len(wf_ex.state_info), 65490)
