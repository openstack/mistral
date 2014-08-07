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

from mistral.db.v2 import api as db_api
from mistral.engine1 import default_engine as d_eng
from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import states


LOG = logging.getLogger(__name__)

WORKBOOK = """
---
Version: '2.0'

Workflows:
  wf1:
    type: reverse
    tasks:
      task1:
        action: std.echo output="{$.param1}"

      task2:
        action: std.echo output="{$.param2}"
        requires: [task1]
"""


class DefaultEngineTest(base.DbTestCase):
    def setUp(self):
        super(DefaultEngineTest, self).setUp()

        wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)

        db_api.create_workbook({
            'name': 'my_wb',
            'description': 'Simple workbook for testing engine.',
            'definition': WORKBOOK,
            'spec': wb_spec.to_dict(),
            'tags': ['test']
        })

        self.engine = d_eng.DefaultEngine()

    def test_start_workflow(self):
        wf_input = {
            'param1': 'Hey',
            'param2': 'Hi'
        }

        exec_db = self.engine.start_workflow(
            'my_wb', 'wf1', wf_input, task_name='task2')

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.RUNNING, exec_db.state)
        self.assertDictEqual(wf_input, exec_db.context)

        self.assertEqual(1, len(exec_db.tasks))

        task_db = exec_db.tasks[0]

        self.assertEqual('task1', task_db.name)
        self.assertEqual(states.RUNNING, task_db.state)
        self.assertIsNotNone(task_db.spec)
        self.assertIsNone(task_db.runtime_context)

        # Data Flow properties.
        self.assertDictEqual(wf_input, task_db.in_context)
        self.assertDictEqual({'output': 'Hey'}, task_db.parameters)

    def test_on_task_result(self):
        # TODO(rakhmerov): Implement.
        pass