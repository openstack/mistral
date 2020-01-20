# Copyright 2019 - Nokia Networks, Inc.
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

from mistral.services import workflows as wf_service
from mistral.tests.unit.api import base
from mistral.tests.unit.engine import base as engine_base

WF_TEXT = """---
        version: "2.0"
        action_wf:
          tasks:
            action_task:
              action: std.noop
        fail_wf:
          tasks:
            fail_task:
              action: std.fail
        middle_wf:
          tasks:
            middle_task:
              workflow: action_wf
            fail_task:
              workflow: fail_wf
        main_wf:
          tasks:
            main_task:
              workflow: middle_wf
        """


class TestSubExecutionsController(base.APITest, engine_base.EngineTestCase):

    def setUp(self):
        super(TestSubExecutionsController, self).setUp()

        wf_service.create_workflows(WF_TEXT)

    def test_sub_executions_wf_ex_id(self):
        wf_ex = self.engine.start_workflow('main_wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/executions' % wf_ex.id)

        self.assertEqual(200, resp.status_int)

        main_wf_ex_list = resp.json['executions']

        self.assertEqual(4, len(main_wf_ex_list))
        self._assert_single_item(main_wf_ex_list, workflow_name='main_wf')
        self._assert_single_item(main_wf_ex_list, workflow_name='action_wf')
        self._assert_single_item(main_wf_ex_list, workflow_name='fail_wf')

        middle_wf = self._assert_single_item(
            main_wf_ex_list,
            workflow_name='middle_wf'
        )

        # check the sub execs of a sub-ex
        resp = self.app.get('/v2/executions/%s/executions' % middle_wf['id'])

        self.assertEqual(200, resp.status_int)

        middle_wf_ex_list = resp.json['executions']

        self.assertEqual(3, len(middle_wf_ex_list))
        self._assert_single_item(middle_wf_ex_list, workflow_name='middle_wf')
        self._assert_single_item(middle_wf_ex_list, workflow_name='action_wf')
        self._assert_single_item(middle_wf_ex_list, workflow_name='fail_wf')

    def test_sub_executions_errors_only(self):
        wf_ex = self.engine.start_workflow('main_wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get(
            '/v2/executions/%s/executions?errors_only=True'
            % wf_ex.id
        )

        self.assertEqual(200, resp.status_int)

        main_wf_ex_list = resp.json['executions']

        self.assertEqual(3, len(main_wf_ex_list))
        self._assert_single_item(main_wf_ex_list, workflow_name='middle_wf')
        self._assert_single_item(main_wf_ex_list, workflow_name='fail_wf')
        self._assert_no_item(main_wf_ex_list, workflow_name='action_wf')

    def test_sub_executions_with_max_depth(self):
        wf_ex = self.engine.start_workflow('main_wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get(
            '/v2/executions/%s/executions?max_depth=1'
            % wf_ex.id
        )

        self.assertEqual(200, resp.status_int)

        main_wf_ex_list = resp.json['executions']

        self.assertEqual(2, len(main_wf_ex_list))
        self._assert_single_item(main_wf_ex_list, workflow_name='middle_wf')
        self._assert_single_item(main_wf_ex_list, workflow_name='main_wf')

    def test_sub_executions_task_id(self):
        wf_ex = self.engine.start_workflow('main_wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get('/v2/executions/%s/executions' % wf_ex.id)

        self.assertEqual(200, resp.status_int)

        main_wf_ex_list = resp.json['executions']

        self.assertEqual(4, len(main_wf_ex_list))
        middle_wf = self._assert_single_item(
            main_wf_ex_list,
            workflow_name='middle_wf'
        )

        resp = self.app.get(
            '/v2/tasks/%s/executions'
            % middle_wf['task_execution_id']
        )

        self.assertEqual(200, resp.status_int)

        main_task_ex_list = resp.json['executions']

        self.assertEqual(3, len(main_task_ex_list))
        self._assert_single_item(main_task_ex_list, workflow_name='fail_wf')
        self._assert_single_item(main_task_ex_list, workflow_name='middle_wf')
        self._assert_single_item(main_task_ex_list, workflow_name='action_wf')

    def test_sub_executions_with_include_output(self):
        wf_ex = self.engine.start_workflow('main_wf')
        self.await_workflow_error(wf_ex.id)

        resp = self.app.get(
            '/v2/executions/%s/executions?include_output=true'
            % wf_ex.id
        )

        self.assertEqual(200, resp.status_int)
        main_wf = self._assert_single_item(
            resp.json['executions'],
            workflow_name='main_wf'
        )

        self.assertIsNotNone(main_wf.get('output'))

        resp = self.app.get('/v2/executions/%s/executions' % wf_ex.id)

        self.assertEqual(200, resp.status_int)

        main_wf = self._assert_single_item(
            resp.json['executions'],
            workflow_name='main_wf'
        )
        self.assertIsNone(main_wf.get('output'))
