# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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
import mock

from oslo.config import cfg

from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.db import api as db_api
from mistral.engine.scalable import engine
from mistral.actions import std_actions
from mistral.engine import states
from mistral.engine import client
from mistral.utils.openstack import keystone


# TODO(rakhmerov): add more tests


LOG = logging.getLogger(__name__)

TOKEN = "123ab"
USER_ID = "321ba"

CONTEXT = {
    'person': {
        'first_name': 'John',
        'last_name': 'Doe',
        'address': {
            'street': '124352 Broadway Street',
            'city': 'Gloomington',
            'country': 'USA'
        }
    }
}

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


def create_workbook(definition_path):
    return db_api.workbook_create({
        'name': 'my_workbook',
        'definition': base.get_resource(definition_path)
    })


@mock.patch.object(
    client.EngineClient, 'start_workflow_execution',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_start_workflow))
@mock.patch.object(
    client.EngineClient, 'convey_task_result',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_task_result))
@mock.patch.object(
    engine.ScalableEngine, '_run_tasks',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
class DataFlowTest(base.EngineTestCase):
    def _check_in_context_execution(self, task):
        self.assertIn('__execution', task['in_context'])

        exec_dict = task['in_context']['__execution']

        self.assertEqual('my_workbook', exec_dict['workbook_name'])
        self.assertEqual(task['execution_id'], exec_dict['id'])
        self.assertIn('task', exec_dict)

    def test_two_dependent_tasks(self):
        CTX = copy.copy(CONTEXT)

        wb = create_workbook('data_flow/two_dependent_tasks.yaml')

        execution = self.engine.start_workflow_execution(wb['name'],
                                                         'build_greeting',
                                                         CTX)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])
        self.assertDictEqual(CTX, execution['context'])

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(2, len(tasks))

        build_full_name_task = \
            self._assert_single_item(tasks, name='build_full_name')
        build_greeting_task = \
            self._assert_single_item(tasks, name='build_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self._check_in_context_execution(build_full_name_task)
        del build_full_name_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['parameters'])
        self.assertDictEqual(
            {
                'f_name': 'John Doe',
                'task': {
                    'build_full_name': {
                        'full_name': 'John Doe'
                    }
                }
            },
            build_full_name_task['output'])

        # Check the second task.
        in_context = CTX
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_greeting_task['parameters'])
        self.assertDictEqual(
            {
                'task': {
                    'build_greeting': {
                        'greeting': 'Hello, John Doe!',
                    }
                }
            },
            build_greeting_task['output'])

        del build_greeting_task['in_context']['task']

        self._check_in_context_execution(build_greeting_task)
        del build_greeting_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_greeting_task['in_context'])

    def test_task_with_two_dependencies(self):
        CTX = copy.copy(CONTEXT)

        wb = create_workbook('data_flow/task_with_two_dependencies.yaml')

        execution = self.engine.start_workflow_execution(wb['name'],
                                                         'send_greeting',
                                                         CTX)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])
        self.assertDictEqual(CTX, execution['context'])

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(3, len(tasks))

        build_full_name_task = \
            self._assert_single_item(tasks, name='build_full_name')
        build_greeting_task = \
            self._assert_single_item(tasks, name='build_greeting')
        send_greeting_task = \
            self._assert_single_item(tasks, name='send_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self._check_in_context_execution(build_full_name_task)
        del build_full_name_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['parameters'])
        self.assertDictEqual(
            {
                'f_name': 'John Doe',
                'task': {
                    'build_full_name': {
                        'full_name': 'John Doe',
                    }
                }
            },
            build_full_name_task['output'])

        # Check the second task.
        in_context = CTX
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({}, build_greeting_task['parameters'])
        self.assertDictEqual(
            {
                'greet_msg': 'Cheers!',
                'task': {
                    'build_greeting': {
                        'greeting': 'Cheers!'
                    }
                }
            },
            build_greeting_task['output'])

        del build_greeting_task['in_context']['task']

        self._check_in_context_execution(build_greeting_task)
        del build_greeting_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_greeting_task['in_context'])

        # Check the third task.
        in_context = CTX
        in_context['f_name'] = 'John Doe'
        in_context['greet_msg'] = 'Cheers!'
        in_context['task'] = {
            'build_greeting': {
                'greeting': 'Cheers!'
            }
        }

        self.assertEqual(states.SUCCESS, send_greeting_task['state'])
        self._check_in_context_execution(send_greeting_task)
        del send_greeting_task['in_context']['__execution']
        self.assertDictEqual(in_context, send_greeting_task['in_context'])
        self.assertDictEqual({'f_name': 'John Doe', 'greet_msg': 'Cheers!'},
                             send_greeting_task['parameters'])
        self.assertDictEqual(
            {
                'task': {
                    'send_greeting': {
                        'greeting_sent': True
                    }
                }
            },
            send_greeting_task['output'])

    def test_two_subsequent_tasks(self):
        CTX = copy.copy(CONTEXT)

        wb = create_workbook('data_flow/two_subsequent_tasks.yaml')

        execution = self.engine.start_workflow_execution(wb['name'],
                                                         'build_full_name',
                                                         CTX)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])
        self.assertDictEqual(CTX, execution['context'])

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(2, len(tasks))

        build_full_name_task = \
            self._assert_single_item(tasks, name='build_full_name')
        build_greeting_task = \
            self._assert_single_item(tasks, name='build_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self._check_in_context_execution(build_full_name_task)
        del build_full_name_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['parameters'])
        self.assertDictEqual(
            {
                'f_name': 'John Doe',
                'task': {
                    'build_full_name': {
                        'full_name': 'John Doe'
                    }
                }
            },
            build_full_name_task['output'])

        # Check the second task.
        in_context = CTX
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_greeting_task['parameters'])
        self.assertDictEqual(
            {
                'greet_msg': 'Hello, John Doe!',
                'task': {
                    'build_greeting': {
                        'greeting': 'Hello, John Doe!',
                    }
                }
            },
            build_greeting_task['output'])

        del build_greeting_task['in_context']['task']

        self._check_in_context_execution(build_greeting_task)
        del build_greeting_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_greeting_task['in_context'])

    def test_three_subsequent_tasks(self):
        CTX = copy.copy(CONTEXT)

        wb = create_workbook('data_flow/three_subsequent_tasks.yaml')

        execution = self.engine.start_workflow_execution(wb['name'],
                                                         'build_full_name',
                                                         CTX)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(states.SUCCESS, execution['state'])
        self.assertDictEqual(CTX, execution['context'])

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(3, len(tasks))

        build_full_name_task = \
            self._assert_single_item(tasks, name='build_full_name')
        build_greeting_task = \
            self._assert_single_item(tasks, name='build_greeting')
        send_greeting_task = \
            self._assert_single_item(tasks, name='send_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self._check_in_context_execution(build_full_name_task)
        del build_full_name_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['parameters'])
        self.assertDictEqual(
            {
                'f_name': 'John Doe',
                'task': {
                    'build_full_name': {
                        'full_name': 'John Doe'
                    }
                }
            },
            build_full_name_task['output'])

        # Check the second task.
        in_context = CTX
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_greeting_task['parameters'])
        self.assertDictEqual(
            {
                'greet_msg': 'Hello, John Doe!',
                'task': {
                    'build_greeting': {
                        'greeting': 'Hello, John Doe!',
                    }
                }
            },
            build_greeting_task['output'])

        del build_greeting_task['in_context']['task']

        self._check_in_context_execution(build_greeting_task)
        del build_greeting_task['in_context']['__execution']
        self.assertDictEqual(CTX, build_greeting_task['in_context'])

        # Check the third task.
        in_context = CTX
        in_context['f_name'] = 'John Doe'
        in_context['greet_msg'] = 'Hello, John Doe!'

        self.assertEqual(states.SUCCESS, send_greeting_task['state'])
        self.assertEqual('John Doe',
                         send_greeting_task['in_context']['f_name'])
        self.assertEqual('Hello, John Doe!',
                         send_greeting_task['in_context']['greet_msg'])
        self.assertDictEqual({'greeting': 'Hello, John Doe!'},
                             send_greeting_task['parameters'])
        self.assertDictEqual(
            {
                'sent': True,
                'task': {
                    'send_greeting': {
                        'greeting_sent': True,
                    }
                }
            },
            send_greeting_task['output'])

        del send_greeting_task['in_context']['task']

        self._check_in_context_execution(send_greeting_task)
        del send_greeting_task['in_context']['__execution']
        self.assertDictEqual(CTX, send_greeting_task['in_context'])

    @mock.patch.object(
        std_actions.HTTPAction, 'run',
        mock.MagicMock(return_value={'state': states.RUNNING}))
    @mock.patch.object(
        keystone, 'client_for_trusts',
        mock.Mock(return_value=mock.MagicMock(user_id=USER_ID,
                                              auth_token=TOKEN)))
    def test_add_token_to_context(self):
        task_name = "create-vms"

        cfg.CONF.pecan.auth_enable = True
        try:
            workbook = create_workbook("test_rest.yaml")
            db_api.workbook_update(workbook['name'], {'trust_id': '123'})

            execution = self.engine.start_workflow_execution(workbook['name'],
                                                             task_name, {})
            tasks = db_api.tasks_get(workbook['name'], execution['id'])

            task = self._assert_single_item(tasks, name=task_name)

            context = task['in_context']

            self.assertIn("auth_token", context)
            self.assertEqual(TOKEN, context['auth_token'])
            self.assertEqual(USER_ID, context["user_id"])

            self.engine.convey_task_result(workbook['name'], execution['id'],
                                           task['id'], states.SUCCESS, {})

            execution = db_api.execution_get(workbook['name'], execution['id'])

            self.assertEqual(states.SUCCESS, execution['state'])
        finally:
            cfg.CONF.pecan.auth_enable = False
