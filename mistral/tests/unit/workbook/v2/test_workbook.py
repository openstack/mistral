# Copyright 2013 - Mirantis, Inc.
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

import yaml

from mistral import exceptions as exc
from mistral.tests.unit.workbook.v2 import base


class WorkbookSpecValidation(base.WorkbookSpecValidationTestCase):

    def test_build_valid_workbook_spec(self):
        wb_spec = self._parse_dsl_spec(dsl_file='my_workbook.yaml')

        # Workbook.
        act_specs = wb_spec.get_actions()
        wf_specs = wb_spec.get_workflows()

        self.assertEqual('2.0', wb_spec.get_version())
        self.assertEqual('my_workbook', wb_spec.get_name())
        self.assertEqual('This is a test workbook', wb_spec.get_description())
        self.assertListEqual(['test', 'v2'], wb_spec.get_tags())
        self.assertIsNotNone(act_specs)
        self.assertIsNotNone(wf_specs)

        # Actions.
        action_spec = act_specs.get('action1')

        self.assertIsNotNone(action_spec)
        self.assertEqual('2.0', action_spec.get_version())
        self.assertEqual('action1', action_spec.get_name())
        self.assertEqual(
            'This is a test ad-hoc action',
            action_spec.get_description()
        )
        self.assertListEqual(['test', 'v2'], action_spec.get_tags())
        self.assertEqual('std.echo', action_spec.get_base())
        self.assertDictEqual(
            {'output': 'Hello <% $.name %>!'},
            action_spec.get_base_input()
        )
        self.assertDictEqual({}, action_spec.get_input())
        self.assertEqual('<% $ %>', action_spec.get_output())

        # Workflows.

        self.assertEqual(2, len(wf_specs))

        wf1_spec = wf_specs.get('wf1')

        self.assertEqual('2.0', wf1_spec.get_version())
        self.assertEqual('wf1', wf1_spec.get_name())
        self.assertEqual(
            'This is a test workflow',
            wf1_spec.get_description()
        )
        self.assertListEqual(['test', 'v2'], wf1_spec.get_tags())
        self.assertEqual('reverse', wf1_spec.get_type())
        self.assertEqual(2, len(wf1_spec.get_tasks()))

        # Tasks.

        task1_spec = wf1_spec.get_tasks().get('task1')

        self.assertIsNotNone(task1_spec)
        self.assertEqual('2.0', task1_spec.get_version())
        self.assertEqual('task1', task1_spec.get_name())
        self.assertEqual('This is a test task', task1_spec.get_description())
        self.assertEqual('action1', task1_spec.get_action_name())
        self.assertEqual({'name': '<% $.name %>'}, task1_spec.get_input())

        policies = task1_spec.get_policies()

        self.assertEqual(2, policies.get_wait_before())
        self.assertEqual(5, policies.get_wait_after())
        self.assertEqual(3, policies.get_concurrency())

        retry_spec = policies.get_retry()

        self.assertEqual(10, retry_spec.get_count())
        self.assertEqual(30, retry_spec.get_delay())
        self.assertEqual('<% $.my_val = 10 %>', retry_spec.get_break_on())

        task2_spec = wf1_spec.get_tasks().get('task2')

        self.assertIsNotNone(task2_spec)
        self.assertEqual('2.0', task2_spec.get_version())
        self.assertEqual('task2', task2_spec.get_name())
        self.assertEqual('std.echo', task2_spec.get_action_name())
        self.assertIsNone(task2_spec.get_workflow_name())
        self.assertEqual(
            {'output': 'Thanks <% $.name %>!'},
            task2_spec.get_input()
        )

        wf2_spec = wf_specs.get('wf2')

        self.assertEqual('2.0', wf2_spec.get_version())
        self.assertEqual('wf2', wf2_spec.get_name())
        self.assertListEqual(['test', 'v2'], wf2_spec.get_tags())
        self.assertEqual('direct', wf2_spec.get_type())
        self.assertEqual(11, len(wf2_spec.get_tasks()))

        task_defaults_spec = wf2_spec.get_task_defaults()

        self.assertListEqual(
            [('fail', '<% $.my_val = 0 %>', {})],
            task_defaults_spec.get_on_error()
        )
        self.assertListEqual(
            [('pause', '', {})],
            task_defaults_spec.get_on_success()
        )
        self.assertListEqual(
            [('succeed', '', {})],
            task_defaults_spec.get_on_complete()
        )

        task3_spec = wf2_spec.get_tasks().get('task3')

        self.assertIsNotNone(task3_spec)
        self.assertEqual('2.0', task3_spec.get_version())
        self.assertEqual('task3', task3_spec.get_name())
        self.assertIsNone(task3_spec.get_action_name())
        self.assertEqual('wf1', task3_spec.get_workflow_name())
        self.assertEqual(
            {
                'name': 'John Doe',
                'age': 32,
                'param1': None,
                'param2': False
            },
            task3_spec.get_input()
        )
        self.assertListEqual(
            [('task4', '<% $.my_val = 1 %>', {})],
            task3_spec.get_on_error()
        )
        self.assertListEqual(
            [('task5', '<% $.my_val = 2 %>', {})],
            task3_spec.get_on_success()
        )
        self.assertListEqual(
            [('task6', '<% $.my_val = 3 %>', {})],
            task3_spec.get_on_complete()
        )

        task7_spec = wf2_spec.get_tasks().get('task7')

        self.assertEqual(
            {
                'is_true': True,
                'object_list': [1, None, 'str'],
                'is_string': '50'
            },
            task7_spec.get_input()
        )

        self.assertEqual(
            {'vm_info': '<% $.vms %>'},
            task7_spec.get_with_items()
        )

        task8_spec = wf2_spec.get_tasks().get('task8')

        self.assertEqual(
            {"itemX": '<% $.arrayI %>', "itemY": '<% $.arrayJ %>'},
            task8_spec.get_with_items()
        )

        self.assertEqual(
            {
                'expr_list': ['<% $.v %>', '<% $.k %>'],
                'expr': '<% $.value %>',
            },
            task8_spec.get_input()
        )

        self.assertEqual('nova', task8_spec.get_target())

        task9_spec = wf2_spec.get_tasks().get('task9')

        self.assertEqual('all', task9_spec.get_join())

        task10_spec = wf2_spec.get_tasks().get('task10')

        self.assertEqual(2, task10_spec.get_join())

        task11_spec = wf2_spec.get_tasks().get('task11')

        self.assertEqual('one', task11_spec.get_join())

        task12_spec = wf2_spec.get_tasks().get('task12')

        self.assertDictEqual(
            {'url': 'http://site.com?q=<% $.query %>', 'params': ''},
            task12_spec.get_input()
        )

        task13_spec = wf2_spec.get_tasks().get('task13')

        self.assertEqual('std.noop', task13_spec.get_action_name())
        self.assertEqual('No-op task', task13_spec.get_description())

    def test_adhoc_action_with_base_in_one_string(self):
        wb_spec = self._parse_dsl_spec(dsl_file='my_workbook.yaml')

        act_specs = wb_spec.get_actions()
        action_spec = act_specs.get("action2")

        self.assertEqual('std.echo', action_spec.get_base())
        self.assertEqual({'output': 'Echo output'},
                         action_spec.get_base_input())

    def test_spec_to_dict(self):
        wb_spec = self._parse_dsl_spec(dsl_file='my_workbook.yaml')

        d = wb_spec.to_dict()

        self.assertEqual('2.0', d['version'])
        self.assertEqual('2.0', d['workflows']['version'])
        self.assertEqual('2.0', d['workflows']['wf1']['version'])

    def test_version_required(self):
        dsl_dict = copy.deepcopy(self._dsl_blank)
        dsl_dict.pop('version', None)

        # TODO(m4dcoder): Check required property error when v1 is deprecated.
        # The version property is not required for v1 workbook whereas it is
        # a required property in v2. For backward compatibility, if no version
        # is not provided, the workbook spec parser defaults to v1 and the
        # required property exception is not triggered. However, a different
        # spec validation error returns due to drastically different schema
        # between workbook versions.
        self.assertRaises(exc.DSLParsingException,
                          self._spec_parser,
                          yaml.safe_dump(dsl_dict))

    def test_version(self):
        tests = [
            ({'version': None}, True),
            ({'version': ''}, True),
            ({'version': '1.0'}, True),
            ({'version': '2.0'}, False),
            ({'version': 2.0}, False),
            ({'version': 2}, False)
        ]

        for version, expect_error in tests:
            self._parse_dsl_spec(changes=version,
                                 expect_error=expect_error)

    def test_name_required(self):
        dsl_dict = copy.deepcopy(self._dsl_blank)
        dsl_dict.pop('name', None)

        exception = self.assertRaises(exc.DSLParsingException,
                                      self._spec_parser,
                                      yaml.safe_dump(dsl_dict))

        self.assertIn("'name' is a required property", exception.message)

    def test_name(self):
        tests = [
            ({'name': ''}, True),
            ({'name': None}, True),
            ({'name': 12345}, True),
            ({'name': 'foobar'}, False)
        ]

        for name, expect_error in tests:
            self._parse_dsl_spec(changes=name,
                                 expect_error=expect_error)

    def test_description(self):
        tests = [
            ({'description': ''}, True),
            ({'description': None}, True),
            ({'description': 12345}, True),
            ({'description': 'This is a test workflow.'}, False)
        ]

        for description, expect_error in tests:
            self._parse_dsl_spec(changes=description,
                                 expect_error=expect_error)

    def test_tags(self):
        tests = [
            ({'tags': ''}, True),
            ({'tags': ['']}, True),
            ({'tags': None}, True),
            ({'tags': 12345}, True),
            ({'tags': ['foo', 'bar']}, False),
            ({'tags': ['foobar', 'foobar']}, True)
        ]

        for tags, expect_error in tests:
            self._parse_dsl_spec(changes=tags,
                                 expect_error=expect_error)

    def test_actions(self):
        actions = {
            'version': '2.0',
            'noop': {
                'base': 'std.noop'
            },
            'echo': {
                'base': 'std.echo'
            }
        }

        tests = [
            ({'actions': []}, True),
            ({'actions': {}}, True),
            ({'actions': None}, True),
            ({'actions': {'version': None}}, True),
            ({'actions': {'version': ''}}, True),
            ({'actions': {'version': '1.0'}}, True),
            ({'actions': {'version': '2.0'}}, False),
            ({'actions': {'version': 2.0}}, False),
            ({'actions': {'version': 2}}, False),
            ({'actions': {'noop': actions['noop']}}, False),
            ({'actions': {'version': '2.0', 'noop': 'std.noop'}}, True),
            ({'actions': actions}, False)
        ]

        for adhoc_actions, expect_error in tests:
            self._parse_dsl_spec(changes=adhoc_actions,
                                 expect_error=expect_error)

    def test_workflows(self):
        workflows = {
            'version': '2.0',
            'wf1': {
                'tasks': {
                    'noop': {
                        'action': 'std.noop'
                    }
                }
            },
            'wf2': {
                'tasks': {
                    'echo': {
                        'action': 'std.echo output="This is a test."'
                    }
                }
            }
        }

        tests = [
            ({'workflows': []}, True),
            ({'workflows': {}}, True),
            ({'workflows': None}, True),
            ({'workflows': {'version': None}}, True),
            ({'workflows': {'version': ''}}, True),
            ({'workflows': {'version': '1.0'}}, True),
            ({'workflows': {'version': '2.0'}}, False),
            ({'workflows': {'version': 2.0}}, False),
            ({'workflows': {'version': 2}}, False),
            ({'workflows': {'wf1': workflows['wf1']}}, False),
            ({'workflows': {'version': '2.0', 'wf1': 'wf1'}}, True),
            ({'workflows': workflows}, False)
        ]

        for workflows, expect_error in tests:
            self._parse_dsl_spec(changes=workflows,
                                 expect_error=expect_error)
