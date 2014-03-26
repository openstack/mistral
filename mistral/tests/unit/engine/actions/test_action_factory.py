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
    'task_spec': {
        'action': 'MyRest:create-vm',
        'parameters': {
            'a': 'b'
        },
        'headers': {
            'Cookie': 'abc'
        },
        'name': 'create-vms'
    },
    'service_spec': {
        'parameters': {
            'baseUrl': 'http://some_host'
        },
        'actions': {
            'create-vm': {
                'parameters': {
                    'url': '/task1'
                }
            }
        },
        'type': 'REST_API',
        'name': 'MyRest'
    },
    'workbook_name': 'wb',
    'execution_id': '1234',
    'id': '123',
    'name': 'create-vms'
}

SAMPLE_SEND_EMAIL_TASK = {
    'name': 'send_email',
    'tags': None,
    'created_at': '2014-02-12 21:40:23.846456',
    'workbook_name': 'myWorkbook',
    'id': '800f52c4-1ba9-45ac-ba81-c4d2a7863738',
    'execution_id': '645f042f-09cb-43ca-bee7-94f592409a7d',
    'state': 'IDLE',
    'service_spec': {
        'type': "SEND_EMAIL",
        'parameters': {
            'smtp_server': "localhost:25",
            'from': "mistral@example.com",
            # use password if smtpd requires TLS authenitcation
            # password: None
        },
        'actions': {
            'send_email': {}
        },
        'name': 'send_email'
    },
    'task_spec': {
        'name': 'backup_user_data',
        'parameters': {
            'to': ["dz@example.com, deg@example.com", "xyz@example.com"],
            'subject': "Multi word subject с русскими буквами",
            'body': "short multiline\nbody\nc русскими буквами",
        },
        'action': 'Email:send_email',
        'service_name': 'Email',
    }
}


class ActionFactoryTest(unittest2.TestCase):
    def test_get_mistral_rest(self):
        task = dict(SAMPLE_TASK)
        task['service_spec'].update({'type': action_types.MISTRAL_REST_API})
        action = action_factory.create_action(task)

        self.assertIn("Mistral-Workbook-Name", action.headers)
        self.assertEqual(action.method, "GET")

    def test_get_rest(self):
        task = dict(SAMPLE_TASK)
        task['service_spec'].update({'type': action_types.REST_API})
        action = action_factory.create_action(task)

        self.assertNotIn("Mistral-Workbook-Name", action.headers)
        self.assertEqual(action.method, "GET")

    def test_get_email(self):
        task = dict(SAMPLE_SEND_EMAIL_TASK)
        action = action_factory.create_action(task)
        self.assertIsNotNone(action)
        #NOTE(dzimine): Implement parameter validation in action,
        # and this will be the only validation we need.
        # Smoke-test one from task and one from service
        for email in task['task_spec']['parameters']['to']:
            self.assertIn(email, action.to)
        self.assertEqual(task['service_spec']['parameters']['smtp_server'],
                         action.smtp_server)
