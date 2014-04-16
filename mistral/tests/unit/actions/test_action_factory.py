# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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
import json
import copy

import unittest2
from mistral.openstack.common import log as logging
from mistral.actions import action_factory as a_f
from mistral.actions import std_actions as std
from mistral.tests import base


LOG = logging.getLogger(__name__)

DB_TASK = {
    'task_spec': {
        'name': 'my_task',
        'action': 'std.http'
    },
    'name': 'my_task',
    'workbook_name': 'my_workbook',
    'execution_id': '123',
    'id': '123',
    'tags': ['deployment', 'test'],
    'parameters': {
        'url': 'http://some.url',
        'params': {
            'param1': 'val1',
            'param2': 'val2'
        },
        'method': 'POST',
        'headers': {
            'content-type': 'text/json'
        },
        'body': {
            'my_object': {
                'prop1': 'val1',
                'prop2': 'val2'
            }
        }
    }
}

DB_TASK_ADHOC = {
    'task_spec': {
        'name': 'my_task',
        'action': 'my_namespace.my_action'
    },
    'action_spec': {
        'name': 'my_action',
        'namespace': 'my_namespace',
        'class': 'std.echo',
        'base-parameters': {
            'output': '{$.first} and {$.second}'
        },
        'parameters': ['first', 'second'],
        'output': {
            'res': '{$}'
        }
    },
    'name': 'my_task',
    'workbook_name': 'my_workbook',
    'execution_id': '123',
    'id': '123',
    'tags': ['deployment', 'test'],
    'parameters': {
        'first': 'Tango',
        'second': 'Cash'
    }
}


class ActionFactoryTest(base.BaseTest):
    def test_register_standard_actions(self):
        namespaces = a_f.get_registered_namespaces()

        self.assertEqual(1, len(namespaces))
        self.assertIn("std", namespaces)

        std_ns = namespaces["std"]

        self.assertEqual(5, len(std_ns))

        self.assertTrue(std_ns.contains_action_name("echo"))
        self.assertTrue(std_ns.contains_action_name("http"))
        self.assertTrue(std_ns.contains_action_name("mistral_http"))
        self.assertTrue(std_ns.contains_action_name("email"))

        self.assertEqual(std.EchoAction, std_ns.get_action_class("echo"))
        self.assertEqual(std.HTTPAction, std_ns.get_action_class("http"))
        self.assertEqual(std.MistralHTTPAction,
                         std_ns.get_action_class("mistral_http"))
        self.assertEqual(std.SendEmailAction,
                         std_ns.get_action_class("email"))

    def test_get_action_class(self):
        self.assertEqual(std.EchoAction, a_f.get_action_class("std.echo"))
        self.assertEqual(std.HTTPAction, a_f.get_action_class("std.http"))
        self.assertEqual(std.SendEmailAction,
                         a_f.get_action_class("std.email"))

    @unittest2.expectedFailure
    def test_get_action_class_failure(self):
        self.assertEqual(std.EchoAction, a_f.get_action_class("echo"))

    def test_create_http_action(self):
        action = a_f.create_action(DB_TASK)

        self.assertIsNotNone(action)

        task_params = DB_TASK['parameters']

        self.assertEqual(task_params['url'], action.url)
        self.assertDictEqual(task_params['params'], action.params)
        self.assertEqual(task_params['method'], action.method)
        self.assertEqual(task_params['headers'], action.headers)
        self.assertDictEqual(task_params['body'], json.loads(action.body))

    def test_create_mistral_http_action(self):
        db_task = copy.copy(DB_TASK)
        db_task['task_spec']['action'] = 'std.mistral_http'

        action = a_f.create_action(db_task)

        self.assertIsNotNone(action)

        task_params = db_task['parameters']

        self.assertEqual(task_params['url'], action.url)
        self.assertDictEqual(task_params['params'], action.params)
        self.assertEqual(task_params['method'], action.method)
        self.assertEqual(task_params['headers'], action.headers)
        self.assertDictEqual(task_params['body'], json.loads(action.body))

        headers = task_params['headers']

        self.assertEqual(db_task['workbook_name'],
                         headers['Mistral-Workbook-Name'])
        self.assertEqual(db_task['execution_id'],
                         headers['Mistral-Execution-Id'])
        self.assertEqual(db_task['id'],
                         headers['Mistral-Task-Id'])

    def test_get_ssh_action(self):
        db_task = copy.copy(DB_TASK)
        db_task['task_spec'] = {
            'name': 'my_task',
            'action': 'std.ssh',
            'parameters': {
                'host': '10.0.0.1',
                'cmd': 'ls -l',
                'username': '$.ssh_username',
                'password': '$.ssh_password'
            }
        }
        db_task['parameters'] = {'host': '10.0.0.1',
                                 'cmd': 'ls -l',
                                 'username': 'ubuntu',
                                 'password': 'ubuntu_password'}

        action = a_f.create_action(db_task)

        self.assertEqual("ubuntu", action.username)
        self.assertEqual("ubuntu_password", action.password)
        self.assertEqual("ls -l", action.cmd)
        self.assertEqual("10.0.0.1", action.host)

    def test_adhoc_echo_action(self):
        db_task = DB_TASK_ADHOC.copy()
        action_spec = db_task['action_spec']

        # With dic-like output formatter.
        action = a_f.create_action(db_task)

        self.assertDictEqual({'res': 'Tango and Cash'}, action.run())

        # With list-like output formatter.
        action_spec['output'] = ['$', '$']

        action = a_f.create_action(db_task)

        self.assertListEqual(['Tango and Cash', 'Tango and Cash'],
                             action.run())

        # With single-object output formatter.
        action_spec['output'] = "'{$}' is a cool movie!"

        action = a_f.create_action(db_task)

        self.assertEqual("'Tango and Cash' is a cool movie!", action.run())
