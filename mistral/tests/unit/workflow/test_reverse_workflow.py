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

from mistral.db.v2.sqlalchemy import models
from mistral.engine1 import states
from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import reverse_workflow as r_wf


LOG = logging.getLogger(__name__)

WORKBOOK = """
---
Version: '2.0'

Workflows:
  wf1:
    type: reverse
    tasks:
      task1:
        action: std.echo output="Hey"

      task2:
        action: std.echo output="Hi!"
        requires: [task1]
"""


class ReverseWorkflowHandlerTest(base.BaseTest):
    def setUp(self):
        super(ReverseWorkflowHandlerTest, self).setUp()

        wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)

        exec_db = models.Execution()
        exec_db.update({
            'id': '1-2-3-4',
            'wf_spec': wb_spec.get_workflows().get('wf1').to_dict(),
            'state': states.IDLE
        })

        self.exec_db = exec_db
        self.handler = r_wf.ReverseWorkflowHandler(exec_db)

    def test_start_workflow(self):
        task_specs = self.handler.start_workflow(task_name='task2')

        self.assertEqual(1, len(task_specs))
        self.assertEqual('task1', task_specs[0].get_name())
        self.assertEqual(states.RUNNING, self.exec_db.state)

    def test_on_task_result_workflow(self):
        # TODO(rakhmerov): Implement.
        pass

    def test_stop_workflow(self):
        # TODO(rakhmerov): Implement.
        pass

    def test_resume_workflow(self):
        # TODO(rakhmerov): Implement.
        pass
