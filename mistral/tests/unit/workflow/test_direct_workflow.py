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
from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import direct_workflow as d_wf
from mistral.workflow import states
from mistral.workflow import utils as wf_utils

LOG = logging.getLogger(__name__)

WORKBOOK = """
---
version: '2.0'

name: my_wb

workflows:
  wf1:
    type: direct

    tasks:
      task1:
        action: std.echo output="Hey"
        publish:
          res1: $
        on-complete:
          - task2: $.res1 = 'Hey'
          - task3: $.res1 = 'Not Hey'

      task2:
        action: std.echo output="Hi"

      task3:
        action: std.echo output="Hoy"
"""


class DirectWorkflowHandlerTest(base.BaseTest):
    def setUp(self):
        super(DirectWorkflowHandlerTest, self).setUp()

        wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)

        exec_db = models.Execution()
        exec_db.update({
            'id': '1-2-3-4',
            'wf_spec': wb_spec.get_workflows().get('wf1').to_dict(),
            'state': states.IDLE
        })

        self.exec_db = exec_db
        self.wb_spec = wb_spec
        self.handler = d_wf.DirectWorkflowHandler(exec_db)

    def _create_db_task(self, id, name, state):
        tasks_spec = self.wb_spec.get_workflows()['wf1'].get_tasks()

        task_db = models.Task()
        task_db.update({
            'id': id,
            'name': name,
            'spec': tasks_spec[name].to_dict(),
            'state': state
        })

        self.exec_db.tasks.append(task_db)

        return task_db

    def test_start_workflow(self):
        commands = self.handler.start_workflow()

        self.assertEqual(1, len(commands))
        self.assertEqual('task1', commands[0].task_spec.get_name())
        self.assertEqual(states.RUNNING, self.exec_db.state)

    def test_on_task_result(self):
        self.exec_db.update({'state': states.RUNNING})

        task1_db = self._create_db_task('1-1-1-1', 'task1', states.RUNNING)

        # Emulate finishing 'task1'.
        commands = self.handler.on_task_result(
            task1_db,
            wf_utils.TaskResult(data='Hey')
        )

        self.assertEqual(1, len(commands))
        self.assertEqual('task2', commands[0].task_spec.get_name())

        self.assertEqual(states.RUNNING, self.exec_db.state)
        self.assertEqual(states.SUCCESS, task1_db.state)

        # Emulate finishing 'task2'.
        task2_db = self._create_db_task('1-1-1-2', 'task2', states.RUNNING)

        commands = self.handler.on_task_result(
            task2_db,
            wf_utils.TaskResult(data='Hi')
        )

        self.assertEqual(0, len(commands))

        self.assertEqual(states.SUCCESS, self.exec_db.state)
        self.assertEqual(states.SUCCESS, task1_db.state)
        self.assertEqual(states.SUCCESS, task2_db.state)

    def test_stop_workflow(self):
        # TODO(rakhmerov): Implement.
        pass

    def test_resume_workflow(self):
        # TODO(rakhmerov): Implement.
        pass
