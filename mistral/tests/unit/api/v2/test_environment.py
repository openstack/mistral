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

from mistral.api.controllers.v2 import environment as api
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
            'conn': 'mysql://admin:secrete@{$.__env.host}/{$.__env.db}'
        }
    }
}

ENVIRONMENT = {
    'id': str(uuid.uuid4()),
    'name': 'test',
    'description': 'my test settings',
    'variables': json.dumps(VARIABLES),
    'scope': 'private',
    'created_at': str(datetime.datetime.utcnow()),
    'updated_at': str(datetime.datetime.utcnow())
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
UPDATED_ENVIRONMENT = copy.deepcopy(ENVIRONMENT)
UPDATED_ENVIRONMENT['variables'] = json.dumps(UPDATED_VARIABLES)
UPDATED_ENVIRONMENT_DB = db.Environment(**ENVIRONMENT_DB_DICT)
UPDATED_ENVIRONMENT_DB.variables = copy.deepcopy(UPDATED_VARIABLES)

MOCK_ENVIRONMENT = mock.MagicMock(return_value=ENVIRONMENT_DB)
MOCK_ENVIRONMENTS = mock.MagicMock(return_value=[ENVIRONMENT_DB])
MOCK_UPDATED_ENVIRONMENT = mock.MagicMock(return_value=UPDATED_ENVIRONMENT_DB)
MOCK_EMPTY = mock.MagicMock(return_value=[])
MOCK_NOT_FOUND = mock.MagicMock(side_effect=exc.NotFoundException())
MOCK_DUPLICATE = mock.MagicMock(side_effect=exc.DBDuplicateEntry())
MOCK_DELETE = mock.MagicMock(return_value=None)


class TestEnvironmentController(base.FunctionalTest):

    def _assert_dict_equal(self, actual, expected):
        self.assertIsInstance(actual, dict)
        self.assertIsInstance(expected, dict)

        if (actual.get('variables') and
                isinstance(actual.get('variables'), basestring)):
            actual['variables'] = json.loads(actual['variables'])

        if (expected.get('variables') and
                isinstance(expected.get('variables'), basestring)):
            expected['variables'] = json.loads(expected['variables'])

        self.assertDictEqual(actual, expected)

    def test_resource(self):
        resource = api.Environment(**copy.deepcopy(ENVIRONMENT))

        actual = resource.to_dict()
        expected = copy.deepcopy(ENVIRONMENT)

        self._assert_dict_equal(actual, expected)

    def test_resource_to_db_model(self):
        resource = api.Environment(**copy.deepcopy(ENVIRONMENT))

        values = resource.to_dict()
        values['variables'] = json.loads(values['variables'])
        values['created_at'] = datetime.datetime.strptime(
            values['created_at'], DATETIME_FORMAT)
        values['updated_at'] = datetime.datetime.strptime(
            values['updated_at'], DATETIME_FORMAT)

        db_model = db.Environment(**values)
        with db_api.transaction():
            db_api.create_environment(db_model)

        self.assertEqual(db_model.id, values['id'])
        self.assertEqual(db_model.name, values['name'])
        self.assertIsNone(db_model.project_id)
        self.assertEqual(db_model.description, values['description'])
        self.assertDictEqual(db_model.variables, values['variables'])
        self.assertEqual(db_model.created_at, values['created_at'])
        self.assertEqual(db_model.updated_at, values['updated_at'])

    @mock.patch.object(db_api, 'get_environments', MOCK_ENVIRONMENTS)
    def test_get_all(self):
        resp = self.app.get('/v2/environments')

        self.assertEqual(resp.status_int, 200)
        self.assertEqual(len(resp.json['environments']), 1)

    def test_get_all_empty(self):
        resp = self.app.get('/v2/environments')

        self.assertEqual(resp.status_int, 200)
        self.assertEqual(len(resp.json['environments']), 0)

    @mock.patch.object(db_api, 'get_environment', MOCK_ENVIRONMENT)
    def test_get(self):
        resp = self.app.get('/v2/environments/123')

        self.assertEqual(resp.status_int, 200)
        self.assertDictEqual(ENVIRONMENT, resp.json)

    @mock.patch.object(db_api, "get_environment", MOCK_NOT_FOUND)
    def test_get_not_found(self):
        resp = self.app.get('/v2/environments/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'create_environment', MOCK_ENVIRONMENT)
    def test_post(self):
        resp = self.app.post_json(
            '/v2/environments',
            copy.deepcopy(ENVIRONMENT))

        self.assertEqual(resp.status_int, 201)

        self._assert_dict_equal(resp.json, copy.deepcopy(ENVIRONMENT))

    @mock.patch.object(db_api, 'create_environment', MOCK_DUPLICATE)
    def test_post_dup(self):
        resp = self.app.post_json(
            '/v2/environments',
            copy.deepcopy(ENVIRONMENT),
            expect_errors=True)

        self.assertEqual(resp.status_int, 409)

    @mock.patch.object(db_api, 'create_environment', MOCK_ENVIRONMENT)
    def test_post_default_scope(self):
        env = copy.deepcopy(ENVIRONMENT)
        del env['scope']

        resp = self.app.post_json('/v2/environments', env)

        self.assertEqual(resp.status_int, 201)

        self._assert_dict_equal(resp.json, copy.deepcopy(ENVIRONMENT))

    @mock.patch.object(db_api, 'update_environment', MOCK_UPDATED_ENVIRONMENT)
    def test_put(self):
        resp = self.app.put_json(
            '/v2/environments',
            copy.deepcopy(UPDATED_ENVIRONMENT))

        self.assertEqual(resp.status_int, 200)

        self._assert_dict_equal(resp.json, copy.deepcopy(UPDATED_ENVIRONMENT))

    @mock.patch.object(db_api, 'update_environment', MOCK_UPDATED_ENVIRONMENT)
    def test_put_default_scope(self):
        env = copy.deepcopy(UPDATED_ENVIRONMENT)
        env['scope'] = None

        resp = self.app.put_json('/v2/environments', env)

        self.assertEqual(resp.status_int, 200)

        self._assert_dict_equal(resp.json, copy.deepcopy(UPDATED_ENVIRONMENT))

    @mock.patch.object(db_api, 'update_environment', MOCK_NOT_FOUND)
    def test_put_not_found(self):
        resp = self.app.put_json(
            '/v2/environments/test',
            copy.deepcopy(UPDATED_ENVIRONMENT),
            expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, 'delete_environment', MOCK_DELETE)
    def test_delete(self):
        resp = self.app.delete('/v2/environments/123')

        self.assertEqual(resp.status_int, 204)

    @mock.patch.object(db_api, 'delete_environment', MOCK_NOT_FOUND)
    def test_delete_not_found(self):
        resp = self.app.delete('/v2/environments/123', expect_errors=True)

        self.assertEqual(resp.status_int, 404)
