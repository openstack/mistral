# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

import copy
import datetime
import mock

from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.tests.unit.api import base

WF_DEFINITION = """
---
version: '2.0'

flow:
  type: direct
  input:
    - param1

  tasks:
    task1:
      action: std.echo output="Hi"
"""

WF_DB = models.WorkflowDefinition(
    name='flow',
    definition=WF_DEFINITION,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    spec={'input': ['param1']}
)

WF = {
    'name': 'flow',
    'definition': WF_DEFINITION,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'input': 'param1'
}

WF_DEFINITION_WITH_INPUT = """
---
version: '2.0'

flow:
  type: direct
  input:
    - param1
    - param2: 2

  tasks:
    task1:
      action: std.echo output="Hi"
"""

WF_DB_WITH_INPUT = models.WorkflowDefinition(
    name='flow',
    definition=WF_DEFINITION_WITH_INPUT,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    spec={'input': ['param1', {'param2': 2}]}
)

WF_WITH_DEFAULT_INPUT = {
    'name': 'flow',
    'definition': WF_DEFINITION_WITH_INPUT,
    'created_at': '1970-01-01 00:00:00',
    'updated_at': '1970-01-01 00:00:00',
    'input': 'param1, param2=2'
}

UPDATED_WF_DEFINITION = """
---
version: '2.0'

flow:
  type: direct
  input:
    - param1
    - param2

  tasks:
    task1:
      action: std.echo output="Hi"
"""

UPDATED_WF_DB = copy.copy(WF_DB)
UPDATED_WF_DB['definition'] = UPDATED_WF_DEFINITION
UPDATED_WF = copy.copy(WF)
UPDATED_WF['definition'] = UPDATED_WF_DEFINITION

WF_DEF_INVALID_MODEL_EXCEPTION = """
---
version: '2.0'

flow:
  type: direct

  tasks:
    task1:
      action: std.echo output="Hi"
      workflow: wf1
"""

WF_DEF_DSL_PARSE_EXCEPTION = """
---
%
"""

WF_DEF_YAQL_PARSE_EXCEPTION = """
---
version: '2.0'

flow:
  type: direct

  tasks:
    task1:
      action: std.echo output=<% * %>
"""

MOCK_WF = mock.MagicMock(return_value=WF_DB)
MOCK_WF_WITH_INPUT = mock.MagicMock(return_value=WF_DB_WITH_INPUT)
MOCK_WFS = mock.MagicMock(return_value=[WF_DB])
MOCK_UPDATED_WF = mock.MagicMock(return_value=UPDATED_WF_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntry())


class TestWorkflowsController(base.FunctionalTest):
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def test_get(self):
        resp = self.app.get('/v2/workflows/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WF, resp.json)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF_WITH_INPUT)
    def test_get_with_input(self):
        resp = self.app.get('/v2/workflows/123')

        self.maxDiff = None

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(WF_WITH_DEFAULT_INPUT, resp.json)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/workflows/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(
        db_api, "create_or_update_workflow_definition", MOCK_UPDATED_WF
    )
    def test_put(self):
        resp = self.app.put(
            '/v2/workflows',
            UPDATED_WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.maxDiff = None

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual({'workflows': [UPDATED_WF]}, resp.json)

    @mock.patch.object(
        db_api, "create_or_update_workflow_definition", MOCK_WF_WITH_INPUT
    )
    def test_put_with_input(self):
        resp = self.app.put(
            '/v2/workflows',
            WF_DEFINITION_WITH_INPUT,
            headers={'Content-Type': 'text/plain'}
        )

        self.maxDiff = None

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual({'workflows': [WF_WITH_DEFAULT_INPUT]}, resp.json)

    @mock.patch.object(
        db_api, "create_or_update_workflow_definition", MOCK_NOT_FOUND
    )
    def test_put_not_found(self):
        resp = self.app.put(
            '/v2/workflows',
            UPDATED_WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True,
        )

        self.assertEqual(resp.status_int, 404)

    def test_put_invalid(self):
        resp = self.app.put(
            '/v2/workflows',
            WF_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 400)
        self.assertIn("Task properties 'action' and 'workflow' "
                      "can't be specified both", resp.body)

    @mock.patch.object(db_api, "create_workflow_definition")
    def test_post(self, mock_mtd):
        mock_mtd.return_value = WF_DB

        resp = self.app.post(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(resp.status_int, 201)
        self.assertDictEqual({'workflows': [WF]}, resp.json)

        mock_mtd.assert_called_once()

        spec = mock_mtd.call_args[0][0]['spec']

        self.assertIsNotNone(spec)
        self.assertEqual(WF_DB.name, spec['name'])

    @mock.patch.object(db_api, "create_workflow_definition", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 409)

    def test_post_invalid(self):
        resp = self.app.post(
            '/v2/workflows',
            WF_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 400)
        self.assertIn("Task properties 'action' and 'workflow' "
                      "can't be specified both", resp.body)

    @mock.patch.object(db_api, "delete_workflow_definition", MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/workflows/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, "delete_workflow_definition", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/workflows/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "get_workflow_definitions", MOCK_WFS)
    def test_get_all(self):
        resp = self.app.get('/v2/workflows')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['workflows']), 1)
        self.assertDictEqual(WF, resp.json['workflows'][0])

    @mock.patch.object(db_api, "get_workflow_definitions", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/workflows')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['workflows']), 0)

    def test_validate(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(resp.status_int, 200)
        self.assertTrue(resp.json['valid'])

    def test_validate_invalid_model_exception(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 200)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Task properties 'action' and 'workflow' "
                      "can't be specified both", resp.json['error'])

    def test_validate_dsl_parse_exception(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEF_DSL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 200)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Definition could not be parsed", resp.json['error'])

    def test_validate_yaql_parse_exception(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEF_YAQL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 200)
        self.assertFalse(resp.json['valid'])
        self.assertIn("unexpected '*' at position 1",
                      resp.json['error'])

    def test_validate_empty(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            '',
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(resp.status_int, 200)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])
