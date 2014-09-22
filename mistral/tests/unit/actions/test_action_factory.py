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

from mistral.actions import std_actions as std
from mistral.openstack.common import log as logging
from mistral.services import action_manager as a_m
from mistral.tests import base
from mistral.workbook import parser as spec_parser

# TODO(rakhmerov): Deprecated. Remove it once engine v1 is gone.

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


class ActionFactoryTest(base.DbTestCase):
    def test_register_standard_actions(self):
        action_list = a_m.get_registered_actions()

        self._assert_single_item(action_list, name="std.echo")
        self._assert_single_item(action_list, name="std.email")
        self._assert_single_item(action_list, name="std.http")
        self._assert_single_item(action_list, name="std.mistral_http")
        self._assert_single_item(action_list, name="std.ssh")

        self._assert_single_item(action_list, name="nova.servers_get")
        self._assert_single_item(action_list, name="nova.volumes_delete")

        self._assert_single_item(action_list, name="keystone.users_list")
        self._assert_single_item(action_list, name="keystone.trusts_create")

        self._assert_single_item(action_list, name="glance.images_list")
        self._assert_single_item(action_list, name="glance.images_delete")

    def test_get_action_class(self):
        self.assertEqual(std.EchoAction, a_m.get_action_class("std.echo"))
        self.assertEqual(std.HTTPAction, a_m.get_action_class("std.http"))
        self.assertEqual(std.MistralHTTPAction,
                         a_m.get_action_class("std.mistral_http"))
        self.assertEqual(std.SendEmailAction,
                         a_m.get_action_class("std.email"))

    def test_resolve_adhoc_action_name(self):
        wb = spec_parser.get_workbook_spec_from_yaml(
            base.get_resource('control_flow/one_sync_task.yaml'))

        action_name = 'MyActions.concat'

        action = a_m.resolve_adhoc_action_name(wb, action_name)

        self.assertEqual('std.echo', action)

    def test_convert_adhoc_action_params(self):
        wb = spec_parser.get_workbook_spec_from_yaml(
            base.get_resource('control_flow/one_sync_task.yaml'))

        action_name = 'MyActions.concat'
        params = {
            'left': 'Stormin',
            'right': 'Stanley'
        }

        parameters = a_m.convert_adhoc_action_params(wb,
                                                     action_name,
                                                     params)

        self.assertEqual({'output': 'Stormin Stanley'}, parameters)

    def test_convert_adhoc_action_result(self):
        wb = spec_parser.get_workbook_spec_from_yaml(
            base.get_resource('control_flow/one_sync_task.yaml'))

        action_name = 'MyActions.concat'
        result = {'output': 'Stormin Stanley'}

        parameters = a_m.convert_adhoc_action_result(wb,
                                                     action_name,
                                                     result)

        self.assertEqual({'string': 'Stormin Stanley'}, parameters)
