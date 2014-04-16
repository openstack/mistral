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

from mistral.actions import std_actions as std
from mistral.tests import base
from mistral.workbook import namespaces as ns

NS_SPEC = {
    'name': 'my_namespace',
    'actions': {
        'my_action': {
            'class': 'std.echo',
            'base-parameters': {
                'output': '{$.first} and {$.second}'
            },
            'parameters': ['first', 'second'],
            'output': {
                'res': '{$}'
            }
        }
    }
}


class AdHocActionTest(base.BaseTest):
    def test_adhoc_echo_action(self):
        ns_raw_spec = copy.copy(NS_SPEC)

        action_spec = ns.NamespaceSpec(ns_raw_spec).actions.get('my_action')

        # With dic-like output formatter.
        action = std.AdHocAction(None, std.EchoAction, action_spec,
                                 first="Tango", second="Cash")

        self.assertDictEqual({'res': 'Tango and Cash'}, action.run())

        # With list-like output formatter.
        ns_raw_spec['actions']['my_action']['output'] = ['$', '$']
        action_spec = ns.NamespaceSpec(ns_raw_spec).actions.get('my_action')

        action = std.AdHocAction(None, std.EchoAction, action_spec,
                                 first="Tango", second="Cash")

        self.assertListEqual(['Tango and Cash', 'Tango and Cash'],
                             action.run())

        # With single-object output formatter.
        ns_raw_spec['actions']['my_action']['output'] =\
            "'{$}' is a cool movie!"
        action_spec = ns.NamespaceSpec(ns_raw_spec).actions.get('my_action')

        action = std.AdHocAction(None, std.EchoAction, action_spec,
                                 first="Tango", second="Cash")

        self.assertEqual("'Tango and Cash' is a cool movie!", action.run())
