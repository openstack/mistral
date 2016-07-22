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
import json
import uuid

import mock
import six

from mistral.api.controllers.v2 import resources
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db
from mistral import exceptions as exc
from mistral.tests.unit.api import base


DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f'

VARIABLES = {
    'host': 'localhost',
    'db': 'test',
    'timeout': 600,
    'verbose': True,
    '__actions': {
        'std.sql': {
            'conn': 'mysql://admin:secrete@<% env().host %>/<% env().db %>'
        }
    }
}

ENVIRONMENT_FOR_CREATE = {
    'name': 'test',
    'description': 'my test settings',
    'variables': VARIABLES,
}

ENVIRONMENT_FOR_UPDATE = {
    'name': 'test',
    'description': 'my test settings',
    'variables': VARIABLES,
    'scope': 'private'
}

ENVIRONMENT_FOR_UPDATE_NO_SCOPE = {
    'name': 'test',
    'description': 'my test settings',
    'variables': VARIABLES
}


ENVIRONMENT = {
    'id': str(uuid.uuid4()),
    'name': 'test',
    'description': 'my test settings',
    'variables': VARIABLES,
    'scope': 'private',
    'created_at': str(datetime.datetime.utcnow()),
    'updated_at': str(datetime.datetime.utcnow())
}

ENVIRONMENT_WITH_ILLEGAL_FIELD = {
    'id': str(uuid.uuid4()),
    'name': 'test',
    'description': 'my test settings',
    'extra_field': 'I can add whatever I want here',
    'variables': VARIABLES,
    'scope': 'private',
}

ENVIRONMENT_DB = db.Environment(
    id=ENVIRONMENT['id'],
    name=ENVIRONMENT['name'],
    description=ENVIRONMENT['description'],
    variables=copy.deepcopy(VARIABLES),
    scope=ENVIRONMENT['scope'],
    created_at=datetime.datetime.strptime(ENVIRONMENT['created_at'],
                                          DATETIME_FORMAT),
    updated_at=datetime.datetime.strptime(ENVIRONMENT['updated_at'],
                                          DATETIME_FORMAT)
)

ENVIRONMENT_DB_DICT = {k: v for k, v in six.iteritems(ENVIRONMENT_DB)}

UPDATED_VARIABLES = copy.deepcopy(VARIABLES)
UPDATED_VARIABLES['host'] = '127.0.0.1'
FOR_UPDATED_ENVIRONMENT = copy.deepcopy(ENVIRONMENT_FOR_UPDATE)
FOR_UPDATED_ENVIRONMENT['variables'] = json.dumps(UPDATED_VARIABLES)
UPDATED_ENVIRONMENT = copy.deepcopy(ENVIRONMENT)
UPDATED_ENVIRONMENT['variables'] = json.dumps(UPDATED_VARIABLES)
UPDATED_ENVIRONMENT_DB = db.Environment(**ENVIRONMENT_DB_DICT)
UPDATED_ENVIRONMENT_DB.variables = copy.deepcopy(UPDATED_VARIABLES)

MOCK_ENVIRONMENT = mock.MagicMock(return_value=ENVIRONMENT_DB)
MOCK_ENVIRONMENTS = mock.MagicMock(return_value=[ENVIRONMENT_DB])
MOCK_UPDATED_ENVIRONMENT = mock.MagicMock(return_value=UPDATED_ENVIRONMENT_DB)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.DBEntityNotFoundError())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntryError())
MOCK_DELETE = mock.MagicMock(return_value=None)


def _convert_vars_to_dict(env_dict):
    """Converts 'variables' in the given environment dict into dictionary."""
    if ('variables' in env_dict and
            isinstance(env_dict.get('variables'), six.string_types)):
        env_dict['variables'] = json.loads(env_dict['variables'])

    return env_dict


def _convert_vars_to_json(env_dict):
    """Converts 'variables' in the given environment dict into string."""
    if ('variables' in env_dict and
            isinstance(env_dict.get('variables'), dict)):
        env_dict['variables'] = json.dumps(env_dict['variables'])

    return env_dict


class TestEnvironmentController(base.APITest):

    def _assert_dict_equal(self, expected, actual):
        self.assertIsInstance(expected, dict)
        self.assertIsInstance(actual, dict)

        _convert_vars_to_dict(expected)
        _convert_vars_to_dict(actual)

        self.assertDictEqual(expected, actual)

    def test_resource(self):
        resource = resources.Environment(**copy.deepcopy(ENVIRONMENT))

        self._assert_dict_equal(
            copy.deepcopy(ENVIRONMENT),
            resource.to_dict()
        )

    @mock.patch.object(db_api, 'get_environments', MOCK_ENVIRONMENTS)
    def test_get_all(self):
        resp = self.app.get('/v2/environments')

        self.assertEqual(200, resp.status_int)
        self.assertEqual(1, len(resp.json['environments']))

    def test_get_all_empty(self):
        resp = self.app.get('/v2/environments')

        self.assertEqual(200, resp.status_int)
        self.assertEqual(0, len(resp.json['environments']))

    @mock.patch.object(db_api, 'get_environment', MOCK_ENVIRONMENT)
    def test_get(self):
        resp = self.app.get('/v2/environments/123')

        self.assertEqual(200, resp.status_int)
        self._assert_dict_equal(ENVIRONMENT, resp.json)

    @mock.patch.object(db_api, "get_environment", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/environments/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, 'create_environment', MOCK_ENVIRONMENT)
    def test_post(self):
        resp = self.app.post_json(
            '/v2/environments',
            _convert_vars_to_json(copy.deepcopy(ENVIRONMENT_FOR_CREATE))
        )

        self.assertEqual(201, resp.status_int)

        self._assert_dict_equal(copy.deepcopy(ENVIRONMENT), resp.json)

    @mock.patch.object(db_api, 'create_environment', MOCK_ENVIRONMENT)
    def test_post_with_illegal_field(self):
        resp = self.app.post_json(
            '/v2/environments',
            _convert_vars_to_json(
                copy.deepcopy(ENVIRONMENT_WITH_ILLEGAL_FIELD)),
            expect_errors=True
        )
        self.assertEqual(400, resp.status_int)

    @mock.patch.object(db_api, 'create_environment', MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post_json(
            '/v2/environments',
            _convert_vars_to_json(copy.deepcopy(ENVIRONMENT_FOR_CREATE)),
            expect_errors=True
        )

        self.assertEqual(409, resp.status_int)

    @mock.patch.object(db_api, 'create_environment', MOCK_ENVIRONMENT)
    def test_post_default_scope(self):
        env = _convert_vars_to_json(copy.deepcopy(ENVIRONMENT_FOR_CREATE))

        resp = self.app.post_json('/v2/environments', env)

        self.assertEqual(201, resp.status_int)

        self._assert_dict_equal(copy.deepcopy(ENVIRONMENT), resp.json)

    @mock.patch.object(db_api, 'update_environment', MOCK_UPDATED_ENVIRONMENT)
    def test_put(self):
        resp = self.app.put_json(
            '/v2/environments',
            copy.deepcopy(FOR_UPDATED_ENVIRONMENT)
        )

        self.assertEqual(200, resp.status_int)

        self._assert_dict_equal(UPDATED_ENVIRONMENT, resp.json)

    @mock.patch.object(db_api, 'update_environment', MOCK_UPDATED_ENVIRONMENT)
    def test_put_default_scope(self):
        env = copy.deepcopy(ENVIRONMENT_FOR_UPDATE_NO_SCOPE)
        env['variables'] = json.dumps(env)

        resp = self.app.put_json('/v2/environments', env)

        self.assertEqual(200, resp.status_int)

        self._assert_dict_equal(copy.deepcopy(UPDATED_ENVIRONMENT), resp.json)

    @mock.patch.object(db_api, 'update_environment', MOCK_NOT_FOUND)
    def test_put_not_found(self):
        env = copy.deepcopy(FOR_UPDATED_ENVIRONMENT)

        resp = self.app.put_json(
            '/v2/environments',
            env,
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch.object(db_api, 'delete_environment', MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/environments/123')

        self.assertEqual(204, resp.status_int)

    @mock.patch.object(db_api, 'delete_environment', MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/environments/123', expect_errors=True)

        self.assertEqual(404, resp.status_int)
