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
from mistral import utils

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
    id='123e4567-e89b-12d3-a456-426655440000',
    name='flow',
    definition=WF_DEFINITION,
    created_at=datetime.datetime(1970, 1, 1),
    updated_at=datetime.datetime(1970, 1, 1),
    spec={'input': ['param1']}
)

WF_DB_SYSTEM = WF_DB.get_clone()
WF_DB_SYSTEM.is_system = True

WF = {
    'id': '123e4567-e89b-12d3-a456-426655440000',
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
UPDATED_WF = copy.deepcopy(WF)
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

WFS_DEFINITION = """
---
version: '2.0'

wf1:
  tasks:
    task1:
      action: std.echo output="Hello"
wf2:
  tasks:
    task1:
      action: std.echo output="Mistral"
"""

MOCK_WF = mock.MagicMock(return_value=WF_DB)
MOCK_WF_SYSTEM = mock.MagicMock(return_value=WF_DB_SYSTEM)
MOCK_WF_WITH_INPUT = mock.MagicMock(return_value=WF_DB_WITH_INPUT)
MOCK_WFS = mock.MagicMock(return_value=[WF_DB])
MOCK_UPDATED_WF = mock.MagicMock(return_value=UPDATED_WF_DB)
MOCK_DELETE = mock.MagicMock(return_value=None)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntryError())


class TestWorkflowsController(base.APITest):
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def test_get(self):
        resp = self.app.get('/v2/workflows/123')

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(WF, resp.json)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF_WITH_INPUT)
    def test_get_with_input(self):
        resp = self.app.get('/v2/workflows/123')

        self.maxDiff = None

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual(WF_WITH_DEFAULT_INPUT, resp.json)

    @mock.patch.object(db_api, "get_workflow_definition", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/workflows/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(
        db_api, "update_workflow_definition", MOCK_UPDATED_WF
    )
    def test_put(self):
        resp = self.app.put(
            '/v2/workflows',
            UPDATED_WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.maxDiff = None

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual({'workflows': [UPDATED_WF]}, resp.json)

    @mock.patch("mistral.services.workflows.update_workflows")
    def test_put_with_uuid(self, update_mock):
        update_mock.return_value = [UPDATED_WF_DB]

        resp = self.app.put(
            '/v2/workflows/123e4567-e89b-12d3-a456-426655440000',
            UPDATED_WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
        update_mock.assert_called_once_with(
            UPDATED_WF_DEFINITION,
            scope='private',
            identifier='123e4567-e89b-12d3-a456-426655440000'
        )
        self.assertDictEqual(UPDATED_WF, resp.json)

    @mock.patch(
        "mistral.db.v2.sqlalchemy.api.get_workflow_definition",
        return_value=WF_DB_SYSTEM
    )
    def test_put_system(self, get_mock):
        resp = self.app.put(
            '/v2/workflows',
            UPDATED_WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            "Attempt to modify a system workflow",
            resp.body.decode()
        )

    @mock.patch.object(db_api, "update_workflow_definition")
    def test_put_public(self, mock_update):
        mock_update.return_value = UPDATED_WF_DB

        resp = self.app.put(
            '/v2/workflows?scope=public',
            UPDATED_WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual({'workflows': [UPDATED_WF]}, resp.json)

        self.assertEqual("public", mock_update.call_args[0][1]['scope'])

    @mock.patch.object(
        db_api, "update_workflow_definition", MOCK_WF_WITH_INPUT
    )
    def test_put_with_input(self):
        resp = self.app.put(
            '/v2/workflows',
            WF_DEFINITION_WITH_INPUT,
            headers={'Content-Type': 'text/plain'}
        )

        self.maxDiff = None

        self.assertEqual(200, resp.status_int)
        self.assertDictEqual({'workflows': [WF_WITH_DEFAULT_INPUT]}, resp.json)

    @mock.patch.object(
        db_api, "update_workflow_definition", MOCK_NOT_FOUND
    )
    def test_put_not_found(self):
        resp = self.app.put(
            '/v2/workflows',
            UPDATED_WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True,
        )

        self.assertEqual(404, resp.status_int)

    def test_put_invalid(self):
        resp = self.app.put(
            '/v2/workflows',
            WF_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn("Invalid DSL", resp.body.decode())

    def test_put_more_workflows_with_uuid(self):
        resp = self.app.put(
            '/v2/workflows/123e4567-e89b-12d3-a456-426655440000',
            WFS_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            "More than one workflows are not supported for update",
            resp.body.decode()
        )

    @mock.patch.object(db_api, "create_workflow_definition")
    def test_post(self, mock_mtd):
        mock_mtd.return_value = WF_DB

        resp = self.app.post(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)
        self.assertDictEqual({'workflows': [WF]}, resp.json)

        self.assertEqual(1, mock_mtd.call_count)

        spec = mock_mtd.call_args[0][0]['spec']

        self.assertIsNotNone(spec)
        self.assertEqual(WF_DB.name, spec['name'])

    @mock.patch.object(db_api, "create_workflow_definition")
    def test_post_public(self, mock_mtd):
        mock_mtd.return_value = WF_DB

        resp = self.app.post(
            '/v2/workflows?scope=public',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)
        self.assertEqual({"workflows": [WF]}, resp.json)

        self.assertEqual("public", mock_mtd.call_args[0][0]['scope'])

    @mock.patch.object(db_api, "create_action_definition")
    def test_post_wrong_scope(self, mock_mtd):
        mock_mtd.return_value = WF_DB

        resp = self.app.post(
            '/v2/workflows?scope=unique',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn("Scope must be one of the following", resp.body.decode())

    @mock.patch.object(db_api, "create_workflow_definition", MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post(
            '/v2/workflows',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(409, resp.status_int)

    def test_post_invalid(self):
        resp = self.app.post(
            '/v2/workflows',
            WF_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn("Invalid DSL", resp.body.decode())

    @mock.patch.object(db_api, "delete_workflow_definition", MOCK_DELETE)
    @mock.patch.object(db_api, "get_workflow_definition", MOCK_WF)
    def test_delete(self):
        resp = self.app.delete('/v2/workflows/123')

        self.assertEqual(204, resp.status_int)

    @mock.patch(
        "mistral.db.v2.sqlalchemy.api.get_workflow_definition",
        return_value=WF_DB_SYSTEM
    )
    def test_delete_system(self, get_mock):
        resp = self.app.delete('/v2/workflows/123', expect_errors=True)

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            "Attempt to delete a system workflow",
            resp.body.decode()
        )

    @mock.patch.object(db_api, "delete_workflow_definition", MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/workflows/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, "get_workflow_definitions", MOCK_WFS)
    def test_get_all(self):
        resp = self.app.get('/v2/workflows')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(1, len(resp.json['workflows']))
        self.assertDictEqual(WF, resp.json['workflows'][0])

    @mock.patch.object(db_api, "get_workflow_definitions", MOCK_EMPTY)
    def test_get_all_empty(self):
        resp = self.app.get('/v2/workflows')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['workflows']))

    @mock.patch.object(db_api, "get_workflow_definitions", MOCK_WFS)
    def test_get_all_pagination(self):
        resp = self.app.get(
            '/v2/workflows?limit=1&sort_keys=id,name')

        self.assertEqual(200, resp.status_int)

        self.assertIn('next', resp.json)

        self.assertEqual(1, len(resp.json['workflows']))
        self.assertDictEqual(WF, resp.json['workflows'][0])

        param_dict = utils.get_dict_from_string(
            resp.json['next'].split('?')[1],
            delimiter='&'
        )

        expected_dict = {
            'marker': '123e4567-e89b-12d3-a456-426655440000',
            'limit': 1,
            'sort_keys': 'id,name',
            'sort_dirs': 'asc,asc',
        }

        self.assertDictEqual(expected_dict, param_dict)

    def test_get_all_pagination_limit_negative(self):
        resp = self.app.get(
            '/v2/workflows?limit=-1&sort_keys=id,name&sort_dirs=asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("Limit must be positive", resp.body.decode())

    def test_get_all_pagination_limit_not_integer(self):
        resp = self.app.get(
            '/v2/workflows?limit=1.1&sort_keys=id,name&sort_dirs=asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("unable to convert to int", resp.body.decode())

    def test_get_all_pagination_invalid_sort_dirs_length(self):
        resp = self.app.get(
            '/v2/workflows?limit=1&sort_keys=id,name&sort_dirs=asc,asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn(
            "Length of sort_keys must be equal or greater than sort_dirs",
            resp.body.decode()
        )

    def test_get_all_pagination_unknown_direction(self):
        resp = self.app.get(
            '/v2/workflows?limit=1&sort_keys=id&sort_dirs=nonexist',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("Unknown sort direction", resp.body.decode())

    @mock.patch('mistral.db.v2.api.get_workflow_definitions')
    def test_get_all_with_fields_filter(self, mock_get_db_wfs):
        mock_get_db_wfs.return_value = [
            ('123e4567-e89b-12d3-a456-426655440000', 'fake_name')
        ]

        resp = self.app.get('/v2/workflows?fields=name')

        self.assertEqual(200, resp.status_int)
        self.assertEqual(1, len(resp.json['workflows']))

        expected_dict = {
            'id': '123e4567-e89b-12d3-a456-426655440000',
            'name': 'fake_name'
        }

        self.assertDictEqual(expected_dict, resp.json['workflows'][0])

    def test_get_all_with_invalid_field(self):
        resp = self.app.get(
            '/v2/workflows?fields=name,nonexist',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn(
            "nonexist are invalid",
            resp.body.decode()
        )

    def test_validate(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEFINITION,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
        self.assertTrue(resp.json['valid'])

    def test_validate_invalid_model_exception(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEF_INVALID_MODEL_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])

    def test_validate_dsl_parse_exception(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEF_DSL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Definition could not be parsed", resp.json['error'])

    def test_validate_yaql_parse_exception(self):
        resp = self.app.post(
            '/v2/workflows/validate',
            WF_DEF_YAQL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
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

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])
