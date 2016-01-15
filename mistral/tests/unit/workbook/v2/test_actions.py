# Copyright 2015 - StackStorm, Inc.
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

from mistral.tests.unit.workbook.v2 import base
from mistral import utils


class ActionSpecValidation(base.WorkbookSpecValidationTestCase):

    def test_base_required(self):
        actions = {'actions': {'a1': {}}}

        exception = self._parse_dsl_spec(changes=actions,
                                         expect_error=True)

        self.assertIn("'base' is a required property", exception.message)

    def test_base(self):
        tests = [
            ({'actions': {'a1': {'base': ''}}}, True),
            ({'actions': {'a1': {'base': None}}}, True),
            ({'actions': {'a1': {'base': 12345}}}, True),
            ({'actions': {'a1': {'base': 'std.noop'}}}, False),
            ({'actions': {'a1': {'base': 'std.echo output="foo"'}}}, False),
            ({'actions': {'a1': {'base': 'std.echo output="<% $.x %>"'}}},
             False),
            ({'actions': {'a1': {'base': 'std.echo output="<% * %>"'}}}, True)
        ]

        for actions, expect_error in tests:
            self._parse_dsl_spec(changes=actions,
                                 expect_error=expect_error)

    def test_base_input(self):
        tests = [
            ({'base-input': {}}, True),
            ({'base-input': None}, True),
            ({'base-input': {'k1': 'v1', 'k2': '<% $.v2 %>'}}, False),
            ({'base-input': {'k1': 'v1', 'k2': '<% * %>'}}, True)
        ]

        actions = {
            'a1': {
                'base': 'foobar'
            }
        }

        for base_inputs, expect_error in tests:
            overlay = {'actions': copy.deepcopy(actions)}
            utils.merge_dicts(overlay['actions']['a1'], base_inputs)
            self._parse_dsl_spec(changes=overlay,
                                 expect_error=expect_error)

    def test_input(self):
        tests = [
            ({'input': ''}, True),
            ({'input': []}, True),
            ({'input': ['']}, True),
            ({'input': None}, True),
            ({'input': ['k1', 'k2']}, False),
            ({'input': ['k1', 12345]}, True),
            ({'input': ['k1', {'k2': 2}]}, False),
            ({'input': [{'k1': 1}, {'k2': 2}]}, False),
            ({'input': [{'k1': None}]}, False),
            ({'input': [{'k1': 1}, {'k1': 1}]}, True),
            ({'input': [{'k1': 1, 'k2': 2}]}, True)
        ]

        actions = {
            'a1': {
                'base': 'foobar'
            }
        }

        for inputs, expect_error in tests:
            overlay = {'actions': copy.deepcopy(actions)}
            utils.merge_dicts(overlay['actions']['a1'], inputs)
            self._parse_dsl_spec(changes=overlay,
                                 expect_error=expect_error)

    def test_output(self):
        tests = [
            ({'output': None}, False),
            ({'output': False}, False),
            ({'output': 12345}, False),
            ({'output': 0.12345}, False),
            ({'output': 'foobar'}, False),
            ({'output': '<% $.x %>'}, False),
            ({'output': '<% * %>'}, True),
            ({'output': ['v1']}, False),
            ({'output': {'k1': 'v1'}}, False)
        ]

        actions = {
            'a1': {
                'base': 'foobar'
            }
        }

        for outputs, expect_error in tests:
            overlay = {'actions': copy.deepcopy(actions)}
            utils.merge_dicts(overlay['actions']['a1'], outputs)
            self._parse_dsl_spec(changes=overlay,
                                 expect_error=expect_error)
