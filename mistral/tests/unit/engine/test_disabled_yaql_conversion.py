# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from unittest import mock

from mistral.actions import std_actions
from mistral.db.v2 import api as db_api
from mistral.engine import engine_server
from mistral import exceptions as exc
from mistral.expressions import yaql_expression
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base as engine_test_base


class DisabledYAQLConversionTest(engine_test_base.EngineTestCase):
    def setUp(self):
        super(DisabledYAQLConversionTest, self).setUp()

        self.override_config('auth_enable', False, 'pecan')

    def test_disabled_yaql_output_conversion(self):
        """Test YAQL expressions with disabled data conversion.

        The test is needed to make sure that if we disable YAQL data
        conversion (for both input and output), then Mistral will handle
        YAQL internal data types properly if they sneak into the Mistral
        logic as part of an expression result. Particularly, we need to
        make sure that the ORM framework (SQLAlchemy) will also be able
        to save data properly if it comes across such a type.

        NOTE:
            - set() and toSet() functions produce "frozenset" type
              internally within YAQL and it should be handled properly
              everywhere in the code including SQLAlchemy.
            - dict() produces "FrozenDict" internally but we unwrap the
              top most dict after evaluating an expression on the Mistral
              side.
        """

        # Both input and output data conversion in YAQL need to be disabled
        # so that we're sure that there won't be any surprises from YAQL
        # like some YAQL internal types included in expression results.
        self.override_config('convert_input_data', False, 'yaql')
        self.override_config('convert_output_data', False, 'yaql')

        # At this point YAQL engine has already been initialized with the
        # default value of config options. So we need to set the corresponding
        # constant to None so it gets initialized again with the new values
        # upon the first use.
        yaql_expression.YAQL_ENGINE = None

        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              publish:
                var1: <% range(0,10) %>
                var2: <% set(15) %>
                var3: <% [4, 5, 6].toSet() %>
                var4: <% {k1 => v1, k2 => v2} %>
                var5: <% dict([['a', 2], ['b', 4]]) %>
                var6: <% [1, dict(k3 => v3, k4 => v4), 3] %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

            t_ex = self._assert_single_item(tasks, name='task1')

            self.assertDictEqual(
                {
                    'var1': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                    'var2': [15],
                    'var3': [4, 5, 6],
                    'var4': {'k1': 'v1', 'k2': 'v2'},
                    'var5': {'a': 2, 'b': 4},
                    'var6': [1, {'k3': 'v3', 'k4': 'v4'}, 3],
                },
                t_ex.published
            )

    def test_configuration_check(self):
        # Kill all the threads started by default and try to start an
        # instance of engine server again with the wrong configuration.
        self.kill_threads()

        self.override_config('convert_input_data', True, 'yaql')
        self.override_config('convert_output_data', False, 'yaql')

        # Setting YAQL engine to None so it reinitialized again with the
        # right values upon the next use.
        yaql_expression.YAQL_ENGINE = None

        eng_svc = engine_server.get_oslo_service(setup_profiler=False)

        self.assertRaisesWithMessage(
            exc.MistralError,
            "The config property 'yaql.convert_output_data' is set to False "
            "so 'yaql.convert_input_data' must also be set to False.",
            eng_svc.start
        )

    def test_root_context(self):
        # Both input and output data conversion in YAQL need to be disabled
        # so that we're sure that there won't be any surprises from YAQL
        # like some YAQL internal types included in expression results.
        self.override_config('convert_input_data', False, 'yaql')
        self.override_config('convert_output_data', False, 'yaql')

        # Setting YAQL engine to None so it reinitialized again with the
        # right values upon the next use.
        yaql_expression.YAQL_ENGINE = None

        wf_text = """---
        version: '2.0'

        wf:
          input:
            - param: default_val

          tasks:
            task1:
              action: std.echo output=<% $ %>
              publish:
                result: <% task().result %>
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            t_ex = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )

            action_ex = t_ex.action_executions[0]

            self.assertTrue(len(action_ex.input) > 0)
            self.assertIn('output', action_ex.input)
            self.assertIn('param', action_ex.input['output'])

    def test_iterators_in_yaql_result(self):
        # Both input and output data conversion in YAQL need to be disabled
        # so that we're sure that there won't be any surprises from YAQL
        # like some YAQL internal types included in expression results.
        self.override_config('convert_input_data', False, 'yaql')
        self.override_config('convert_output_data', False, 'yaql')

        # Setting YAQL engine to None so it reinitialized again with the
        # right values upon the next use.
        yaql_expression.YAQL_ENGINE = None

        wf_text = """---
        version: '2.0'

        wf:
          input:
            - params: null

          tasks:
            task1:
              action: std.echo
              input:
                output:
                  param1:
                    <% switch($.params = null => [],
                    $.params != null =>
                    $.params.items().select({k => $[0], v => $[1]})) %>
        """

        wf_service.create_workflows(wf_text)

        wf_input = {
            'params': {
                'k1': 'v1',
                'k2': 'v2'
            }
        }

        with mock.patch.object(self.executor, 'run_action',
                               wraps=self.executor.run_action) as mocked:
            # Start workflow.
            wf_ex = self.engine.start_workflow('wf', wf_input=wf_input)

            self.await_workflow_success(wf_ex.id)

            with db_api.transaction():
                # Note: We need to reread execution to access related tasks.
                wf_ex = db_api.get_workflow_execution(wf_ex.id)

                t_ex = self._assert_single_item(
                    wf_ex.task_executions,
                    name='task1'
                )

                action_ex = t_ex.action_executions[0]

                self.assertTrue(len(action_ex.input) > 0)

            mocked.assert_called_once()

            # We need to make sure that the executor got the right action
            # input regardless of an iterator (that can only be used once)
            # present in the YAQL expression result. Let's check first 4
            # actual arguments with the executor was called, including the
            # action parameters.
            args = mocked.call_args[0]

            self.assertIsInstance(args[0], std_actions.EchoAction)
            self.assertEqual(action_ex.id, args[1])
