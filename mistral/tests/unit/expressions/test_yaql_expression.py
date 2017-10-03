# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

import datetime
from mistral import exceptions as exc
from mistral.expressions import yaql_expression as expr
from mistral.tests.unit import base
from mistral import utils
import mock

DATA = {
    "server": {
        "id": "03ea824a-aa24-4105-9131-66c48ae54acf",
        "name": "cloud-fedora",
        "status": "ACTIVE"
    },
    "status": "OK"
}

SERVERS = {
    "servers": [
        {'name': 'centos'},
        {'name': 'ubuntu'},
        {'name': 'fedora'}
    ]
}


class YaqlEvaluatorTest(base.BaseTest):
    def setUp(self):
        super(YaqlEvaluatorTest, self).setUp()

        self._evaluator = expr.YAQLEvaluator()

    def test_expression_result(self):
        res = self._evaluator.evaluate('$.server', DATA)
        self.assertEqual({
            'id': "03ea824a-aa24-4105-9131-66c48ae54acf",
            'name': 'cloud-fedora',
            'status': 'ACTIVE'
        }, res)

        res = self._evaluator.evaluate('$.server.id', DATA)
        self.assertEqual('03ea824a-aa24-4105-9131-66c48ae54acf', res)

        res = self._evaluator.evaluate("$.server.status = 'ACTIVE'", DATA)
        self.assertTrue(res)

    def test_wrong_expression(self):
        res = self._evaluator.evaluate("$.status = 'Invalid value'", DATA)
        self.assertFalse(res)

        self.assertRaises(
            exc.YaqlEvaluationException,
            self._evaluator.evaluate,
            '$.wrong_key',
            DATA
        )

        expression_str = 'invalid_expression_string'
        res = self._evaluator.evaluate(expression_str, DATA)
        self.assertEqual(expression_str, res)

    def test_select_result(self):
        res = self._evaluator.evaluate(
            '$.servers.where($.name = ubuntu)',
            SERVERS
        )
        item = list(res)[0]
        self.assertEqual({'name': 'ubuntu'}, item)

    def test_function_string(self):
        self.assertEqual('3', self._evaluator.evaluate('str($)', '3'))
        self.assertEqual('3', self._evaluator.evaluate('str($)', 3))

    def test_function_len(self):
        self.assertEqual(3, self._evaluator.evaluate('len($)', 'hey'))
        data = [{'some': 'thing'}]

        self.assertEqual(
            1,
            self._evaluator.evaluate('$.where($.some = thing).len()', data)
        )

    def test_validate(self):
        self._evaluator.validate('abc')
        self._evaluator.validate('1')
        self._evaluator.validate('1 + 2')
        self._evaluator.validate('$.a1')
        self._evaluator.validate('$.a1 * $.a2')

    def test_validate_failed(self):
        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          '*')

        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          [1, 2, 3])

        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          {'a': 1})

    def test_function_json_pp(self):
        self.assertEqual('"3"', self._evaluator.evaluate('json_pp($)', '3'))
        self.assertEqual('3', self._evaluator.evaluate('json_pp($)', 3))
        self.assertEqual(
            '[\n    1,\n    2\n]',
            self._evaluator.evaluate('json_pp($)', [1, 2])
        )
        self.assertEqual(
            '{\n    "a": "b"\n}',
            self._evaluator.evaluate('json_pp($)', {'a': 'b'})
        )
        self.assertEqual(
            '"Mistral\nis\nawesome"',
            self._evaluator.evaluate(
                'json_pp($)', '\n'.join(['Mistral', 'is', 'awesome'])
            )
        )

    def test_function_uuid(self):
        uuid = self._evaluator.evaluate('uuid()', {})

        self.assertTrue(utils.is_valid_uuid(uuid))

    @mock.patch('mistral.db.v2.api.get_task_executions')
    @mock.patch('mistral.workflow.data_flow.get_task_execution_result')
    def test_filter_tasks_without_task_execution(self, task_execution_result,
                                                 task_executions):

        task_execution_result.return_value = 'task_execution_result'
        time_now = utils.utc_now_sec()
        task = type("obj", (object,), {
            'id': 'id',
            'name': 'name',
            'published': 'published',
            'result': task_execution_result(),
            'spec': 'spec',
            'state': 'state',
            'state_info': 'state_info',
            'type': 'type',
            'workflow_execution_id': 'workflow_execution_id',
            'created_at': time_now,
            'updated_at': time_now + datetime.timedelta(seconds=1),
        })()

        task_executions.return_value = [task]

        ctx = {
            '__task_execution': None,
            '__execution': {
                'id': 'some'
            }
        }

        result = self._evaluator.evaluate('tasks(some)', ctx)

        self.assertEqual(1, len(result))
        self.assertDictEqual({
            'id': task.id,
            'name': task.name,
            'published': task.published,
            'result': task.result,
            'spec': task.spec,
            'state': task.state,
            'state_info': task.state_info,
            'type': task.type,
            'workflow_execution_id': task.workflow_execution_id,
            'created_at': task.created_at.isoformat(' '),
            'updated_at': task.updated_at.isoformat(' ')
        }, result[0])

    def test_function_env(self):
        ctx = {'__env': 'some'}

        self.assertEqual(ctx['__env'], self._evaluator.evaluate('env()', ctx))


class InlineYAQLEvaluatorTest(base.BaseTest):
    def setUp(self):
        super(InlineYAQLEvaluatorTest, self).setUp()

        self._evaluator = expr.InlineYAQLEvaluator()

    def test_multiple_placeholders(self):
        expr_str = """
            Statistics for tenant "<% $.project_id %>"

            Number of virtual machines: <% $.vm_count %>
            Number of active virtual machines: <% $.active_vm_count %>
            Number of networks: <% $.net_count %>

            -- Sincerely, Mistral Team.
        """

        result = self._evaluator.evaluate(
            expr_str,
            {
                'project_id': '1-2-3-4',
                'vm_count': 28,
                'active_vm_count': 0,
                'net_count': 1
            }
        )

        expected_result = """
            Statistics for tenant "1-2-3-4"

            Number of virtual machines: 28
            Number of active virtual machines: 0
            Number of networks: 1

            -- Sincerely, Mistral Team.
        """

        self.assertEqual(expected_result, result)

    def test_single_value_casting(self):
        self.assertEqual(3, self._evaluator.evaluate('<% $ %>', 3))
        self.assertEqual('33', self._evaluator.evaluate('<% $ %><% $ %>', 3))

    def test_function_string(self):
        self.assertEqual('3', self._evaluator.evaluate('<% str($) %>', '3'))
        self.assertEqual('3', self._evaluator.evaluate('<% str($) %>', 3))

    def test_validate(self):
        self._evaluator.validate('There is no expression.')
        self._evaluator.validate('<% abc %>')
        self._evaluator.validate('<% 1 %>')
        self._evaluator.validate('<% 1 + 2 %>')
        self._evaluator.validate('<% $.a1 %>')
        self._evaluator.validate('<% $.a1 * $.a2 %>')
        self._evaluator.validate('<% $.a1 %> is <% $.a2 %>')
        self._evaluator.validate('The value is <% $.a1 %>.')

    def test_validate_failed(self):
        self.assertRaises(exc.YaqlGrammarException,
                          self._evaluator.validate,
                          'The value is <% * %>.')

        self.assertRaises(exc.YaqlEvaluationException,
                          self._evaluator.validate,
                          [1, 2, 3])

        self.assertRaises(exc.YaqlEvaluationException,
                          self._evaluator.validate,
                          {'a': 1})
