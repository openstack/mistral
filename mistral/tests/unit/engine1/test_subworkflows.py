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

from mistral.db.v2 import api as db_api
from mistral.openstack.common import log as logging
from mistral.tests.unit.engine1 import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import states

LOG = logging.getLogger(__name__)

WORKBOOK = """
---
Version: '2.0'

Workflows:
  wf1:
    type: reverse
    parameters:
      - param1
      - param2
    output:
      final_result: $.final_result

    tasks:
      task1:
        action: std.echo output="{$.param1}"
        publish:
          result1: $

      task2:
        action: std.echo output="'{$.param1} & {$.param2}'"
        publish:
          final_result: $
        requires: [task1]

  wf2:
    type: direct
    start_task: task1
    output:
      slogan: $.slogan

    tasks:
      task1:
        workflow: my_wb.wf1 param1='Bonnie' param2='Clyde'
        workflow_parameters:
            task_name: task2
        publish:
          slogan: "{$.final_result} is a cool movie!"
"""


class SubworkflowsTest(base.EngineTestCase):
    def setUp(self):
        super(SubworkflowsTest, self).setUp()

        wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)

        db_api.create_workbook({
            'name': 'my_wb',
            'description': 'Simple workbook for testing engine.',
            'definition': WORKBOOK,
            'spec': wb_spec.to_dict(),
            'tags': ['test']
        })

    def test_subworkflow(self):
        exec1_db = self.engine.start_workflow('my_wb', 'wf2', None)

        # Execution 1.
        self.assertIsNotNone(exec1_db)
        self.assertDictEqual({}, exec1_db.input)
        self.assertDictEqual({}, exec1_db.start_params)

        db_execs = db_api.get_executions()

        self.assertEqual(2, len(db_execs))

        # Execution 2.
        exec2_db = db_execs[0] if db_execs[0].id != exec1_db.id \
            else db_execs[1]

        self.assertIsNotNone(exec2_db.parent_task_id)
        self.assertDictEqual(
            {
                'task_name': 'task2',
                'parent_task_id': exec2_db.parent_task_id
            },
            exec2_db.start_params
        )
        self.assertDictEqual(
            {
                'param1': 'Bonnie',
                'param2': 'Clyde'
            },
            exec2_db.input
        )

        # Wait till workflow 'wf1' is completed.
        self._await(
            lambda: db_api.get_execution(exec2_db.id).state == states.SUCCESS,
        )

        exec2_db = db_api.get_execution(exec2_db.id)

        self.assertDictEqual(
            {
                'final_result': "'Bonnie & Clyde'"
            },
            exec2_db.output
        )

        # Wait till workflow 'wf2' is completed.
        self._await(
            lambda: db_api.get_execution(exec1_db.id).state == states.SUCCESS,
        )

        exec1_db = db_api.get_execution(exec1_db.id)

        self.assertEqual(
            "'Bonnie & Clyde' is a cool movie!",
            exec1_db.context['slogan']
        )

        self.assertDictEqual(
            {
                'slogan': "'Bonnie & Clyde' is a cool movie!"
            },
            exec1_db.output
        )
