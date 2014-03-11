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

from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.db import api as db_api
from mistral.engine.local import engine
from mistral.engine import states

# TODO(rakhmerov): add more tests

LOG = logging.getLogger(__name__)

ENGINE = engine.get_engine()()

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


def create_workbook(definition_path):
    return db_api.workbook_create({
        'name': 'my_workbook',
        'definition': base.get_resource(definition_path)
    })


class DataFlowTest(base.DbTestCase):
    def _get_task(self, tasks, name):
        for t in tasks:
            if t['name'] == name:
                return t

        self.fail("Task not found [name=%s]" % name)

    def test_two_dependent_tasks(self):
        wb = create_workbook('data_flow/two_dependent_tasks.yaml')

        execution = ENGINE.start_workflow_execution(wb['name'],
                                                    'build_greeting',
                                                    CONTEXT)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertDictEqual(execution['context'], CONTEXT)

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(2, len(tasks))

        build_full_name_task = self._get_task(tasks, 'build_full_name')
        build_greeting_task = self._get_task(tasks, 'build_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self.assertDictEqual(CONTEXT, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['input'])
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
        in_context = CONTEXT.copy()
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_greeting_task['input'])
        self.assertDictEqual(
            {
                'task': {
                    'build_greeting': {
                        'greeting': 'Hello, John Doe!',
                    }
                }
            },
            build_greeting_task['output'])

        del build_greeting_task['in_context']['f_name']
        del build_greeting_task['in_context']['task']

        self.assertDictEqual(CONTEXT, build_greeting_task['in_context'])

    def test_task_with_two_dependencies(self):
        wb = create_workbook('data_flow/task_with_two_dependencies.yaml')

        execution = ENGINE.start_workflow_execution(wb['name'],
                                                    'send_greeting',
                                                    CONTEXT)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertDictEqual(execution['context'], CONTEXT)

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(3, len(tasks))

        build_full_name_task = self._get_task(tasks, 'build_full_name')
        build_greeting_task = self._get_task(tasks, 'build_greeting')
        send_greeting_task = self._get_task(tasks, 'send_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self.assertDictEqual(CONTEXT, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['input'])
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
        in_context = CONTEXT.copy()
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({}, build_greeting_task['input'])
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

        del build_greeting_task['in_context']['f_name']
        del build_greeting_task['in_context']['task']

        self.assertDictEqual(CONTEXT, build_greeting_task['in_context'])

        # Check the third task.
        in_context = CONTEXT.copy()
        in_context['f_name'] = 'John Doe'
        in_context['greet_msg'] = 'Cheers!'
        in_context['task'] = {
            'build_greeting': {
                'greeting': 'Cheers!'
            }
        }

        self.assertEqual(states.SUCCESS, send_greeting_task['state'])
        self.assertDictEqual(in_context, send_greeting_task['in_context'])
        self.assertDictEqual({'f_name': 'John Doe', 'greet_msg': 'Cheers!'},
                             send_greeting_task['input'])
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
        wb = create_workbook('data_flow/two_subsequent_tasks.yaml')

        execution = ENGINE.start_workflow_execution(wb['name'],
                                                    'build_full_name',
                                                    CONTEXT)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertDictEqual(execution['context'], CONTEXT)

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(2, len(tasks))

        build_full_name_task = self._get_task(tasks, 'build_full_name')
        build_greeting_task = self._get_task(tasks, 'build_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self.assertDictEqual(CONTEXT, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['input'])
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
        in_context = CONTEXT.copy()
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_greeting_task['input'])
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

        del build_greeting_task['in_context']['f_name']
        del build_greeting_task['in_context']['task']

        self.assertDictEqual(CONTEXT, build_greeting_task['in_context'])

    def test_three_subsequent_tasks(self):
        wb = create_workbook('data_flow/three_subsequent_tasks.yaml')

        execution = ENGINE.start_workflow_execution(wb['name'],
                                                    'build_full_name',
                                                    CONTEXT)

        # We have to reread execution to get its latest version.
        execution = db_api.execution_get(execution['workbook_name'],
                                         execution['id'])

        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertDictEqual(execution['context'], CONTEXT)

        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self.assertEqual(3, len(tasks))

        build_full_name_task = self._get_task(tasks, 'build_full_name')
        build_greeting_task = self._get_task(tasks, 'build_greeting')
        send_greeting_task = self._get_task(tasks, 'send_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self.assertDictEqual(CONTEXT, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['input'])
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
        in_context = CONTEXT.copy()
        in_context['f_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertEqual('John Doe',
                         build_greeting_task['in_context']['f_name'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_greeting_task['input'])
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

        del build_greeting_task['in_context']['f_name']
        del build_greeting_task['in_context']['task']

        self.assertDictEqual(CONTEXT, build_greeting_task['in_context'])

        # Check the third task.
        in_context = CONTEXT.copy()
        in_context['f_name'] = 'John Doe'
        in_context['greet_msg'] = 'Hello, John Doe!'

        self.assertEqual(states.SUCCESS, send_greeting_task['state'])
        self.assertEqual('John Doe',
                         send_greeting_task['in_context']['f_name'])
        self.assertEqual('Hello, John Doe!',
                         send_greeting_task['in_context']['greet_msg'])
        self.assertDictEqual({'greeting': 'Hello, John Doe!'},
                             send_greeting_task['input'])
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

        del send_greeting_task['in_context']['f_name']
        del send_greeting_task['in_context']['greet_msg']
        del send_greeting_task['in_context']['task']

        self.assertDictEqual(CONTEXT, send_greeting_task['in_context'])
