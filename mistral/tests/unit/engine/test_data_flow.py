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

        if tasks[0]['name'] == 'build_full_name':
            build_full_name_task = tasks[0]
            build_greeting_task = tasks[1]
        else:
            build_full_name_task = tasks[1]
            build_greeting_task = tasks[0]

        self.assertEqual(build_full_name_task['name'], 'build_full_name')
        self.assertEqual(build_greeting_task['name'], 'build_greeting')

        # Check the first task.
        self.assertEqual(states.SUCCESS, build_full_name_task['state'])
        self.assertDictEqual(CONTEXT, build_full_name_task['in_context'])
        self.assertDictEqual({'first_name': 'John', 'last_name': 'Doe'},
                             build_full_name_task['input'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_full_name_task['output'])

        # Check the second task.
        in_context = CONTEXT.copy()
        in_context['full_name'] = 'John Doe'

        self.assertEqual(states.SUCCESS, build_greeting_task['state'])
        self.assertDictEqual(in_context, build_greeting_task['in_context'])
        self.assertDictEqual({'full_name': 'John Doe'},
                             build_greeting_task['input'])
        self.assertDictEqual({'greeting': 'Hello, John Doe!'},
                             build_greeting_task['output'])

        # TODO(rakhmerov): add more checks
