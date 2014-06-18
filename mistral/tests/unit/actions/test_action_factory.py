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

import copy
import json

from mistral.actions import action_factory as a_f
from mistral.actions import std_actions as std
from mistral.engine import data_flow
from mistral import exceptions
from mistral.openstack.common import log as logging
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
    'in_context': {},
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
    'in_context': {},
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

    def test_get_action_class_failure(self):
        exc = self.assertRaises(exceptions.ActionException,
                                a_f.get_action_class, 'echo')
        self.assertIn('Invalid action name', exc.message)

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

    def test_create_adhoc_action_with_openstack_context(self):
        db_task = copy.copy(DB_TASK_ADHOC)
        db_task['action_spec']['output'] = {'res': '{$}'}
        db_task['in_context'].update({
            'openstack': {
                'auth_token': '123',
                'project_id': '321'
            }
        })
        base_parameters = db_task['action_spec']['base-parameters']
        base_parameters['output'] = ("{$.openstack.auth_token}"
                                     "{$.openstack.project_id}")

        action = a_f.create_action(db_task)

        self.assertEqual({'res': "123321"}, action.run())

    def test_create_adhoc_action_no_openstack_context(self):
        db_task = copy.copy(DB_TASK_ADHOC)
        db_task['action_spec']['output'] = {'res': '{$}'}
        db_task['in_context'].update({
            'openstack': None
        })
        base_parameters = db_task['action_spec']['base-parameters']
        base_parameters['output'] = "$.openstack.auth_token"

        action = a_f.create_action(db_task)

        self.assertEqual({'res': "$.openstack.auth_token"}, action.run())

    def test_create_no_adhoc_action_with_openstack_context(self):
        db_task = copy.copy(DB_TASK)
        db_task['task_spec']['action'] = 'std.http'
        db_task['in_context'].update({
            'openstack': {
                'auth_token': '123',
                'project_id': '321'
            }
        })
        ## In case of no-adhoc action we should evaluate task parameters
        ## to see what we need.
        task_spec = db_task['task_spec']
        task_spec['parameters'] = {
            'url': "http://some/{$.openstack.project_id}/servers",
        }

        db_task['parameters'] = data_flow.evaluate_task_parameters(
            db_task, db_task['in_context'])

        action = a_f.create_action(db_task)

        self.assertEqual("http://some/321/servers", action.url)

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
        db_task = copy.copy(DB_TASK_ADHOC)
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
