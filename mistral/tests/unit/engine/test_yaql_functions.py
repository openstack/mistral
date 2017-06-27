# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base as engine_test_base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class YAQLFunctionsEngineTest(engine_test_base.EngineTestCase):
    def test_task_function(self):
        wf_text = """---
        version: '2.0'

        wf:
          type: direct

          tasks:
            task1:
              description: This is task 1
              tags: ['t1']
              action: std.echo output=1
              publish:
                name: <% task(task1).name %>
                description: <% task(task1).spec.description %>
                tags: <% task(task1).spec.tags%>
                state: <% task(task1).state %>
                state_info: <% task(task1).state_info %>
                res: <% task(task1).result %>
              on-success:
                - task2

            task2:
              action: std.echo output=<% task(task1).result + 1 %>
              publish:
                name: <% task(task1).name %>
                description: <% task(task1).spec.description %>
                tags: <% task(task1).spec.tags%>
                state: <% task(task1).state %>
                state_info: <% task(task1).state_info %>
                res: <% task(task1).result %>
                task2_res: <% task(task2).result %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        self.assertEqual(states.SUCCESS, wf_ex.state)

        task1 = self._assert_single_item(
            tasks,
            name='task1',
            state=states.SUCCESS
        )
        task2 = self._assert_single_item(
            tasks,
            name='task2',
            state=states.SUCCESS
        )

        self.assertDictEqual(
            {
                'name': 'task1',
                'description': 'This is task 1',
                'tags': ['t1'],
                'state': states.SUCCESS,
                'state_info': None,
                'res': 1
            },
            task1.published
        )
        self.assertDictEqual(
            {
                'name': 'task1',
                'description': 'This is task 1',
                'tags': ['t1'],
                'state': states.SUCCESS,
                'state_info': None,
                'res': 1,
                'task2_res': 2
            },
            task2.published
        )

    def test_task_function_returns_null(self):
        wf_text = """---
            version: '2.0'

            wf:
              output:
                task2: <% task(task2) %>
                task2bool: <% task(task2) = null %>

              tasks:
                task1:
                  action: std.noop
                  on-success:
                    - task2: <% false %>

                task2:
                  action: std.noop
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertDictEqual(
                {
                    'task2': None,
                    'task2bool': True
                },
                wf_ex.output
            )

            task_execs = wf_ex.task_executions

        self.assertEqual(1, len(task_execs))

    def test_task_function_non_existing(self):
        wf_text = """---
            version: '2.0'

            wf:
              type: direct
              output:
                task_name: <% task(non_existing_task).name %>

              tasks:
                task1:
                  action: std.noop
            """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        self.assertEqual(states.ERROR, wf_ex.state)
        self.assertIn('non_existing_task', wf_ex.state_info)

    def test_task_function_no_arguments(self):
        wf_text = """---
            version: '2.0'

            wf:
              tasks:
                task1:
                  action: std.echo output=1
                  publish:
                    task1_id: <% task().id %>
                    task1_result:  <% task().result %>
                    task1_state: <% task().state %>
                  on-success: task2

                task2:
                  action: std.echo output=2
                  publish:
                    task2_id: <% task().id %>
                    task2_result:  <% task().result %>
                    task2_state: <% task().state %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task1_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )
            task2_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task2'
            )

            self.assertDictEqual(
                {
                    'task1_id': task1_ex.id,
                    'task1_result': 1,
                    'task1_state': states.SUCCESS
                },
                task1_ex.published
            )
            self.assertDictEqual(
                {
                    'task2_id': task2_ex.id,
                    'task2_result': 2,
                    'task2_state': states.SUCCESS
                },
                task2_ex.published
            )

        # The internal data needed for evaluation of the task() function
        # should not be persisted to DB.
        self.assertNotIn('__task_execution', task1_ex.in_context)
        self.assertNotIn('__task_execution', task2_ex.in_context)

    def test_task_function_no_name_on_complete_case(self):
        wf_text = """---
            version: '2.0'

            wf:
              tasks:
                task1:
                  action: std.echo output=1
                  on-complete:
                    - fail(msg=<% task() %>)
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_error(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertEqual(states.ERROR, wf_ex.state)
            self.assertIsNotNone(wf_ex.state_info)
            self.assertIn(wf_ex.id, wf_ex.state_info)

    def test_task_function_no_name_on_success_case(self):
        wf_text = """---
            version: '2.0'

            wf:
              tasks:
                task1:
                  action: std.echo output=1
                  on-success:
                    - task2: <% task().result = 1 %>
                    - task3: <% task().result = 100 %>

                task2:
                  action: std.echo output=2

                task3:
                  action: std.echo output=3
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertEqual(2, len(wf_ex.task_executions))
            self._assert_single_item(wf_ex.task_executions, name='task1')
            self._assert_single_item(wf_ex.task_executions, name='task2')

    def test_uuid_function(self):
        wf_text = """---
            version: '2.0'

            wf:
              tasks:
                task1:
                  action: std.echo output=<% uuid() %>
                  publish:
                    result: <% task(task1).result %>
            """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = task_execs[0]

        result = task_ex.published['result']

        self.assertIsNotNone(result)
        self.assertEqual(36, len(result))
        self.assertEqual(4, result.count('-'))

    def test_execution_function(self):
        wf_text = """---
            version: '2.0'

            wf:
              input:
                - k1
                - k2: v2_default

              tasks:
                task1:
                  action: std.echo output=<% execution() %>
                  publish:
                    result: <% task(task1).result %>
            """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow(
            'wf',
            wf_input={'k1': 'v1'},
            param1='blablabla'
        )

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_execs = wf_ex.task_executions

        task_ex = task_execs[0]

        execution = task_ex.published['result']

        self.assertIsInstance(execution, dict)

        spec = execution['spec']

        self.assertEqual('2.0', spec['version'])
        self.assertEqual('wf', spec['name'])
        self.assertIn('tasks', spec)
        self.assertEqual(1, len(spec['tasks']))

        self.assertDictEqual(
            {
                'k1': 'v1',
                'k2': 'v2_default'
            },
            execution['input']
        )

        self.assertDictEqual(
            {
                'param1': 'blablabla',
                'namespace': '',
                'env': {}
            },
            execution['params']
        )

        self.assertEqual(
            wf_ex.created_at.isoformat(' '),
            execution['created_at']
        )

    def test_yaml_dump_function(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              publish:
                data: <% {key1 => foo, key2 => bar} %>
              on-success: task2

            task2:
              publish:
                yaml_str: <% yaml_dump($.data) %>
                json_str: <% json_dump($.data) %>
        """

        wf_service.create_workflows(wf_text)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction(read_only=True):
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task2'
            )

            yaml_str = task_ex.published['yaml_str']
            json_str = task_ex.published['json_str']

        self.assertIsNotNone(yaml_str)
        self.assertIn('key1: foo', yaml_str)
        self.assertIn('key2: bar', yaml_str)

        self.assertIsNotNone(json_str)
        self.assertIn('"key1": "foo"', json_str)
        self.assertIn('"key2": "bar"', json_str)
