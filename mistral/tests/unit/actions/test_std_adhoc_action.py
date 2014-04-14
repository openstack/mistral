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
from mistral.tests import base

NS_SPEC = {
    'my_namespace': {
        'my_action': {
            'class': 'std.echo',
            'base-parameters': {
                'output': '{$.first} and {$.second}'
            },
            'parameters': ['first', 'second'],
            'output': {
                'res': '{$.base_output}'
            }
        }
    }
}


class AdHocActionTest(base.BaseTest):
    def test_adhoc_echo_action(self):
        action_spec = NS_SPEC['my_namespace']['my_action'].copy()

        # With dic-like output formatter.
        action = std.AdHocAction(None, std.EchoAction, action_spec,
                                 first="Tango", second="Cash")

        self.assertDictEqual({'res': 'Tango and Cash'}, action.run())

        # With list-like output formatter.
        action_spec['output'] = ['$.base_output', '$.base_output']

        action = std.AdHocAction(None, std.EchoAction, action_spec,
                                 first="Tango", second="Cash")

        self.assertListEqual(['Tango and Cash', 'Tango and Cash'],
                             action.run())

        # With single-object output formatter.
        action_spec['output'] = "'{$.base_output}' is a cool movie!"

        action = std.AdHocAction(None, std.EchoAction, action_spec,
                                 first="Tango", second="Cash")

        self.assertEqual("'Tango and Cash' is a cool movie!", action.run())
