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

import unittest2

from mistral.engine.actions import action_factory
from mistral.engine.actions import action_types


SAMPLE_TASK = {
    'task_dsl': {
        'action': 'MyRest:create-vm',
        'parameters': {
            'a': 'b'
        },
        'headers': {
            'Cookie': 'abc'
        }
    },
    'service_dsl': {
        'parameters': {
            'baseUrl': 'http://some_host'
        },
        'actions': {
            'create-vm': {
                'parameters': {
                    'url': '/task1'
                }
            }
        }
    },
    'workbook_name': 'wb',
    'execution_id': '1234',
    'id': '123'
}


class ActionFactoryTest(unittest2.TestCase):
    def test_get_mistral_rest(self):
        task = dict(SAMPLE_TASK)
        task['service_dsl'].update({'type': action_types.MISTRAL_REST_API})
        action = action_factory.create_action(task)

        self.assertIn("Mistral-Workbook-Name", action.headers)
        self.assertEqual(action.method, "GET")

    def test_get_rest(self):
        task = dict(SAMPLE_TASK)
        task['service_dsl'].update({'type': action_types.REST_API})
        action = action_factory.create_action(task)

        self.assertNotIn("Mistral-Workbook-Name", action.headers)
        self.assertEqual(action.method, "GET")
