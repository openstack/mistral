# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import mock
import pkg_resources as pkg

from mistral.db import api as db_api
from mistral.engine.single import actions
from mistral.engine.single import engine
from mistral.engine import states
from mistral import version
from mistral.tests.unit import base as test_base


class TestWorkflow(test_base.DbTestCase):
    def setUp(self):
        super(TestWorkflow, self).setUp()
        self.cfg_prefix = "tests/resources/"
        db_api.workbook_get = mock.MagicMock(
            return_value={'definition': self.get_cfg("test_rest.yaml")})

    def get_cfg(self, cfg_suffix):
        return open(pkg.resource_filename(
            version.version_info.package,
            self.cfg_prefix + cfg_suffix)).read()

    def test_load_workflow(self):
        workflow = engine._get_workflow("my_workbook", "create-vms")
        self.assertEqual(workflow.target_task, "create-vms")
        self.assertEqual(len(workflow.tasks), 1)
        self.assertEqual(len(workflow._graph.nodes()), 1)

    def test_run_workflow(self):
        actions.RestAPIAction.run = mock.MagicMock(return_value="result")
        workflow = engine._get_workflow("my_workbook", "create-vms")
        execution = db_api.execution_create("my_workbook", {
            'state': 'RUNNING',
            'target_task': 'create-vms'
        })
        workflow.execution = execution
        workflow.create_tasks()
        workflow.run_resolved_tasks()
        task = db_api.tasks_get("my_workbook", execution['id'])[0]
        db_api.task_update("my_workbook", execution['id'],
                           task['id'], {'state': states.SUCCESS})
        self.assertEqual(workflow.results, {"create-vms": "result"})
