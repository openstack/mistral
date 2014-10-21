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

from mistral import exceptions
from mistral.tests import base
from mistral.workbook import parser as spec_parser

VALID_WB = """
---
version: '2.0'

name: my_workbook
description: This is a test workbook
tags: [test, v2]

actions:
  action1:
    description: This is a test ad-hoc action
    tags: [test, v2]
    base: std.echo
    base-input:
        output: "Hello {$.name}!"
    output: $

  action2:
    description: This is a test ad-hoc action with base params
    tags: [test, v2]
    base: std.echo output="Echo output"
    output: $

workflows:
  wf1:
    description: This is a test workflow
    tags: [test, v2]
    type: reverse

    input:
      - name

    tasks:
      task1:
        description: This is a test task
        action: action1 name="{$.name}"
        policies:
          wait-before: 2
          wait-after: 5
          retry:
            count: 10
            delay: 30
            break-on: $.my_val = 10

      task2:
        requires: [task1]
        action: std.echo output="Thanks {$.name}!"

  wf2:
    tags: [test, v2]
    type: direct

    task-defaults:
      policies:
        retry:
          count: 10
          delay: 30
          break-on: $.my_val = 10
      on-error:
        - fail: $.my_val = 0
      on-success:
        - pause
      on-complete:
        - succeed

    tasks:
      task3:
        workflow: wf1 name="John Doe" age=32 param1=null param2=false
        on-error:
          - task4: $.my_val = 1
        on-success:
          - task5: $.my_val = 2
        on-complete:
          - task6: $.my_val = 3

      task4:
        action: std.echo output="Task 4 echo"

      task5:
        action: std.echo output="Task 5 echo"

      task6:
        action: std.echo output="Task 6 echo"

      task7:
        for-each:
          vm_info: $.vms
        workflow: wf2 is_true=true object_list=[1, null, "str"]

      task8:
        workflow: wf2 expr_list=["$.value", "{$.key}"] expr={$.value}
        targets: [nova]
"""


INVALID_WB = """
version: 2.0

name: wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hey!"
        for-each:
          vms: 3

"""


# TODO(rakhmerov): Add more tests when v2 spec is complete.
# TODO(rakhmerov): Add negative tests.


class DSLv2ModelTest(base.BaseTest):
    def setUp(self):
        super(DSLv2ModelTest, self).setUp()

    def test_build_valid_workbook_spec(self):
        wb_spec = spec_parser.get_workbook_spec_from_yaml(VALID_WB)

        # Workbook.
        act_specs = wb_spec.get_actions()
        wf_specs = wb_spec.get_workflows()
        tr_specs = wb_spec.get_triggers()

        self.assertEqual('2.0', wb_spec.get_version())
        self.assertEqual('my_workbook', wb_spec.get_name())
        self.assertEqual('This is a test workbook', wb_spec.get_description())
        self.assertListEqual(['test', 'v2'], wb_spec.get_tags())
        self.assertIsNotNone(act_specs)
        self.assertIsNotNone(wf_specs)
        self.assertIsNone(tr_specs)

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
            {'output': 'Hello {$.name}!'},
            action_spec.get_base_input()
        )
        self.assertListEqual([], action_spec.get_input())
        self.assertEqual('$', action_spec.get_output())

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
        self.assertEqual({'name': '{$.name}'}, task1_spec.get_input())

        policies = task1_spec.get_policies()

        self.assertEqual(2, policies.get_wait_before())
        self.assertEqual(5, policies.get_wait_after())

        retry_spec = policies.get_retry()

        self.assertEqual(10, retry_spec.get_count())
        self.assertEqual(30, retry_spec.get_delay())
        self.assertEqual('$.my_val = 10', retry_spec.get_break_on())

        task2_spec = wf1_spec.get_tasks().get('task2')

        self.assertIsNotNone(task2_spec)
        self.assertEqual('2.0', task2_spec.get_version())
        self.assertEqual('task2', task2_spec.get_name())
        self.assertEqual('std.echo', task2_spec.get_action_name())
        self.assertIsNone(task2_spec.get_workflow_name())
        self.assertEqual(
            {'output': 'Thanks {$.name}!'},
            task2_spec.get_input()
        )

        wf2_spec = wf_specs.get('wf2')

        self.assertEqual('2.0', wf2_spec.get_version())
        self.assertEqual('wf2', wf2_spec.get_name())
        self.assertListEqual(['test', 'v2'], wf2_spec.get_tags())
        self.assertEqual('direct', wf2_spec.get_type())
        self.assertEqual(6, len(wf2_spec.get_tasks()))

        task_defaults_spec = wf2_spec.get_task_defaults()

        self.assertListEqual(
            [('fail', '$.my_val = 0')],
            task_defaults_spec.get_on_error()
        )
        self.assertListEqual(
            [('pause', '')],
            task_defaults_spec.get_on_success()
        )
        self.assertListEqual(
            [('succeed', '')],
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
            [('task4', '$.my_val = 1')],
            task3_spec.get_on_error()
        )
        self.assertListEqual(
            [('task5', '$.my_val = 2')],
            task3_spec.get_on_success()
        )
        self.assertListEqual(
            [('task6', '$.my_val = 3')],
            task3_spec.get_on_complete()
        )

        task7_spec = wf2_spec.get_tasks().get('task7')

        self.assertEqual(
            {
                'is_true': True,
                'object_list': [1, None, 'str'],
            },
            task7_spec.get_input()
        )

        self.assertEqual(
            {'vm_info': '$.vms'},
            task7_spec.get_for_each()
        )

        task8_spec = wf2_spec.get_tasks().get('task8')

        self.assertEqual(
            {
                'expr_list': ['$.value', '{$.key}'],
                'expr': '{$.value}',
            },
            task8_spec.get_input()
        )

        self.assertEqual(['nova'], task8_spec.get_targets())

    def test_adhoc_action_with_base_in_one_string(self):
        wb_spec = spec_parser.get_workbook_spec_from_yaml(VALID_WB)

        act_specs = wb_spec.get_actions()
        action_spec = act_specs.get("action2")

        self.assertEqual("std.echo", action_spec.get_base())
        self.assertEqual({'output': 'Echo output'},
                         action_spec.get_base_input())

    def test_invalid_for_each(self):
        exc = self.assertRaises(
            exceptions.InvalidModelException,
            spec_parser.get_workbook_spec_from_yaml,
            INVALID_WB
        )
        self.assertIn("for-each", str(exc))

    def test_to_dict(self):
        wb_spec = spec_parser.get_workbook_spec_from_yaml(VALID_WB)

        d = wb_spec.to_dict()

        self.assertEqual('2.0', d['version'])
        self.assertEqual('2.0', d['workflows']['version'])
        self.assertEqual('2.0', d['workflows']['wf1']['version'])
