#  Copyright 2019 - Nokia Corporation
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from mistral.services import workflows as wf_service
from mistral.tests.unit.api import base
from mistral.tests.unit.engine import base as engine_base

WF_TEXT = """---
version: '2.0'

wf:
  tasks:
       task1:
         action: std.noop
         on-success:
           publish:
             branch:
               my_var: Branch local value
             global:
               my_var: Global value
           next:
             - task2

       task2:
         action: std.noop
         publish:
           local: <% $.my_var %>
           global: <% global(my_var) %>

"""


def _find_task(task_name, tasks):
    return next(
        (
            task
            for task in tasks
            if task['name'] == task_name
        ), None
    )


class TestGlobalPublish(base.APITest, engine_base.EngineTestCase):
    def setUp(self):
        super(TestGlobalPublish, self).setUp()

        wf_service.create_workflows(WF_TEXT)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        self.wf_id = wf_ex.id

    def test_global_publish_in_task_exec(self):
        resp = self.app.get('/v2/tasks/')

        tasks = resp.json['tasks']
        task = _find_task('task1', tasks)

        self.assertIsNotNone(task, 'task1 not found')

        resp = self.app.get('/v2/tasks/%s/' % task['id'])

        self.assert_for_published_global(resp)

    def test_global_publish_in_wf_exec(self):
        resp = self.app.get('/v2/executions/%s/' % self.wf_id)

        self.assert_for_published_global(resp)

    def assert_for_published_global(self, resp):
        self.assertEqual(200, resp.status_int)
        self.assertEqual(
            resp.json['published_global'],
            '{"my_var": "Global value"}'
        )
