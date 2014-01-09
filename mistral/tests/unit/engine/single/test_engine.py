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


class TestEngine(test_base.DbTestCase):
    def setUp(self):
        super(TestEngine, self).setUp()
        self.cfg_prefix = "tests/resources/"
        self.wb_name = "my_workbook"
        self.workbook_get = db_api.workbook_get

    def tearDown(self):
        super(TestEngine, self).tearDown()
        db_api.workbook_get = self.workbook_get

    def get_cfg(self, cfg_suffix):
        return open(pkg.resource_filename(
            version.version_info.package,
            self.cfg_prefix + cfg_suffix)).read()

    def test_engine_one_task(self):
        db_api.workbook_get = mock.MagicMock(
            return_value={'definition': self.get_cfg("test_rest.yaml")})
        actions.RestAPIAction.run = mock.MagicMock(return_value="result")
        execution = engine.start_workflow_execution(self.wb_name,
                                                    "create-vms")
        task = db_api.tasks_get(self.wb_name, execution['id'])[0]
        engine.convey_task_result(self.wb_name, execution['id'], task['id'],
                                  states.SUCCESS, None)
        task = db_api.tasks_get(self.wb_name, execution['id'])[0]
        execution = db_api.execution_get(self.wb_name, execution['id'])
        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(task['state'], states.SUCCESS)

    def test_engine_multiple_tasks(self):
        db_api.workbook_get = mock.MagicMock(
            return_value={'definition': self.get_cfg("test_rest.yaml")})
        actions.RestAPIAction.run = mock.MagicMock(return_value="result")
        execution = engine.start_workflow_execution(self.wb_name,
                                                    "backup-vms")
        tasks = db_api.tasks_get(self.wb_name, execution['id'])
        engine.convey_task_result(self.wb_name, execution['id'],
                                  tasks[0]['id'],
                                  states.SUCCESS, None)
        tasks = db_api.tasks_get(self.wb_name, execution['id'])

        self.assertEqual(tasks[0]['state'], states.SUCCESS)

        engine.convey_task_result(self.wb_name, execution['id'],
                                  tasks[1]['id'],
                                  states.SUCCESS, None)
        tasks = db_api.tasks_get(self.wb_name, execution['id'])
        execution = db_api.execution_get(self.wb_name, execution['id'])
        self.assertEqual(execution['state'], states.SUCCESS)
        self.assertEqual(tasks[1]['state'], states.SUCCESS)
