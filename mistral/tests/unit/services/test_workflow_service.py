# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

import copy

from oslo_config import cfg

from mistral.db.v2.sqlalchemy import api as db_api
from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.tests.unit import base
from mistral import utils
from mistral.workbook import parser as spec_parser
from mistral.workflow import states


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

WORKFLOW = """
---
version: '2.0'

list_servers:

  tasks:
    list_servers:
      action: nova.servers_list

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

    def test_update_non_existing_workflow_failed(self):
        exception = self.assertRaises(
            exc.DBEntityNotFoundError,
            wf_service.update_workflows,
            WORKFLOW
        )

        self.assertIn("Workflow not found", exception.message)

    def test_invalid_workflow_list(self):
        exception = self.assertRaises(
            exc.InvalidModelException,
            wf_service.create_workflows,
            INVALID_WORKFLOW
        )

        self.assertIn("Invalid DSL", exception.message)

    def test_update_workflow_execution_env(self):
        wf_exec_template = {
            'spec': {},
            'start_params': {'task': 'my_task1'},
            'state': 'PAUSED',
            'state_info': None,
            'params': {'env': {'k1': 'abc'}},
            'created_at': None,
            'updated_at': None,
            'context': {'__env': {'k1': 'fee fi fo fum'}},
            'task_id': None,
            'trust_id': None,
            'description': None,
            'output': None
        }

        states_permitted = [
            states.IDLE,
            states.PAUSED,
            states.ERROR
        ]

        update_env = {'k1': 'foobar'}

        for state in states_permitted:
            wf_exec = copy.deepcopy(wf_exec_template)
            wf_exec['state'] = state

            with db_api.transaction():
                created = db_api.create_workflow_execution(wf_exec)

                self.assertIsNone(created.updated_at)

                updated = wf_service.update_workflow_execution_env(
                    created,
                    update_env
                )

            self.assertDictEqual(update_env, updated.params['env'])
            self.assertDictEqual(update_env, updated.context['__env'])

            fetched = db_api.get_workflow_execution(created.id)

            self.assertEqual(updated, fetched)
            self.assertIsNotNone(fetched.updated_at)

    def test_update_workflow_execution_env_wrong_state(self):
        wf_exec_template = {
            'spec': {},
            'start_params': {'task': 'my_task1'},
            'state': 'PAUSED',
            'state_info': None,
            'params': {'env': {'k1': 'abc'}},
            'created_at': None,
            'updated_at': None,
            'context': {'__env': {'k1': 'fee fi fo fum'}},
            'task_id': None,
            'trust_id': None,
            'description': None,
            'output': None
        }

        states_not_permitted = [
            states.RUNNING,
            states.RUNNING_DELAYED,
            states.SUCCESS,
            states.WAITING
        ]

        update_env = {'k1': 'foobar'}

        for state in states_not_permitted:
            wf_exec = copy.deepcopy(wf_exec_template)
            wf_exec['state'] = state

            with db_api.transaction():
                created = db_api.create_workflow_execution(wf_exec)

                self.assertIsNone(created.updated_at)

                self.assertRaises(
                    exc.NotAllowedException,
                    wf_service.update_workflow_execution_env,
                    created,
                    update_env
                )

            fetched = db_api.get_workflow_execution(created.id)

            self.assertDictEqual(
                wf_exec['params']['env'],
                fetched.params['env']
            )

            self.assertDictEqual(
                wf_exec['context']['__env'],
                fetched.context['__env']
            )
