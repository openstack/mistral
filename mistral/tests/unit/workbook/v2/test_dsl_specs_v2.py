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

from mistral.tests import base
from mistral.workbook import parser as spec_parser

VALID_WB = """
---
Version: '2.0'

Namespaces:
  ns1:
    actions:
      action1:
        class: std.echo
        base-parameters:
            output: "Hello {$.name}!"

Workflows:
  wf1:
    type: reverse

    parameters:
      - name
      - age

    tasks:
      task1:
        action: ns1.action1 name="{$.name}"

      task2:
        requires: [task1]
        action: std.echo output="Thanks {$.name}!"

  wf2:
    type: direct

    tasks:
      task3:
        workflow: wf1 name="John Doe" age=32
"""

# TODO(rakhmerov): Add more tests when v2 spec is complete.
# TODO(rakhmerov): Add negative tests.


class DSLv2ModelTest(base.BaseTest):
    def setUp(self):
        super(DSLv2ModelTest, self).setUp()

    def test_build_valid_workbook_spec(self):
        wb_spec = spec_parser.get_workbook_spec_from_yaml(VALID_WB)

        # Workbook.
        ns_specs = wb_spec.get_namespaces()
        wf_specs = wb_spec.get_workflows()
        tr_specs = wb_spec.get_triggers()

        self.assertEqual('2.0', wb_spec.get_version())
        self.assertIsNotNone(ns_specs)
        self.assertIsNotNone(wf_specs)
        self.assertIsNone(tr_specs)

        # Namespaces.
        self.assertEqual(1, len(ns_specs))

        ns_spec = ns_specs.get('ns1')

        self.assertIsNotNone(ns_spec)
        self.assertEqual('2.0', ns_spec.get_version())
        self.assertEqual('ns1', ns_spec.get_name())
        self.assertIsNone(ns_spec.get_class())
        self.assertIsNone(ns_spec.get_base_parameters())
        self.assertIsNone(ns_spec.get_parameters())

        action_specs = ns_spec.get_actions()

        self.assertEqual(1, len(action_specs))

        # Actions.
        action_spec = action_specs.get('action1')

        self.assertIsNotNone(action_spec)
        self.assertEqual('2.0', action_spec.get_version())
        self.assertEqual('action1', action_spec.get_name())
        self.assertEqual('std.echo', action_spec.get_class())
        self.assertDictEqual(
            {'output': 'Hello {$.name}!'},
            action_spec.get_base_parameters()
        )
        self.assertDictEqual({}, action_spec.get_parameters())
        self.assertIsNone(action_spec.get_output())

        # Workflows.

        self.assertEqual(2, len(wf_specs))

        wf1_spec = wf_specs.get('wf1')

        self.assertEqual('2.0', wf1_spec.get_version())
        self.assertEqual('wf1', wf1_spec.get_name())
        self.assertEqual('reverse', wf1_spec.get_type())
        self.assertEqual(2, len(wf1_spec.get_tasks()))

        # Tasks.

        task1_spec = wf1_spec.get_tasks().get('task1')

        self.assertIsNotNone(task1_spec)
        self.assertEqual('2.0', task1_spec.get_version())
        self.assertEqual('task1', task1_spec.get_name())
        self.assertEqual('ns1.action1', task1_spec.get_action_name())
        self.assertEqual('action1', task1_spec.get_short_action_name())
        self.assertEqual({'name': '{$.name}'}, task1_spec.get_parameters())

        task2_spec = wf1_spec.get_tasks().get('task2')

        self.assertIsNotNone(task2_spec)
        self.assertEqual('2.0', task2_spec.get_version())
        self.assertEqual('task2', task2_spec.get_name())
        self.assertEqual('std.echo', task2_spec.get_action_name())
        self.assertEqual('echo', task2_spec.get_short_action_name())
        self.assertEqual('std', task2_spec.get_action_namespace())
        self.assertIsNone(task2_spec.get_workflow_name())
        self.assertIsNone(task2_spec.get_short_workflow_name())
        self.assertIsNone(task2_spec.get_workflow_namespace())
        self.assertEqual(
            {'output': 'Thanks {$.name}!'},
            task2_spec.get_parameters()
        )

        wf2_spec = wf_specs.get('wf2')

        self.assertEqual('2.0', wf2_spec.get_version())
        self.assertEqual('wf2', wf2_spec.get_name())
        self.assertEqual('direct', wf2_spec.get_type())
        self.assertEqual(1, len(wf2_spec.get_tasks()))

        task3_spec = wf2_spec.get_tasks().get('task3')

        self.assertIsNotNone(task3_spec)
        self.assertEqual('2.0', task3_spec.get_version())
        self.assertEqual('task3', task3_spec.get_name())
        self.assertIsNone(task3_spec.get_action_name())
        self.assertIsNone(task3_spec.get_short_action_name())
        self.assertIsNone(task3_spec.get_action_namespace())
        self.assertEqual('wf1', task3_spec.get_workflow_name())
        self.assertEqual('wf1', task3_spec.get_short_workflow_name())
        self.assertIsNone(task3_spec.get_workflow_namespace())
        self.assertEqual(
            {'name': 'John Doe', 'age': '32'},
            task3_spec.get_parameters()
        )

    def test_to_dict(self):
        wb_spec = spec_parser.get_workbook_spec_from_yaml(VALID_WB)

        d = wb_spec.to_dict()

        self.assertEqual('2.0', d['Version'])
        self.assertEqual('2.0', d['Workflows']['Version'])
        self.assertEqual('2.0', d['Workflows']['wf1']['Version'])
