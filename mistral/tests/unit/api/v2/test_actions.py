# Copyright 2014 - Mirantis, Inc.
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
from unittest import mock

import sqlalchemy as sa

from mistral.actions import adhoc
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models
from mistral.lang import parser as spec_parser
from mistral.services import adhoc_actions
from mistral.tests.unit.api import base

from mistral_lib.actions.providers import composite
from mistral_lib import utils


ADHOC_ACTION_YAML_A = """
---
version: '2.0'

a_action:
  description: My super cool action.
  tags: ['test', 'v2']
  base: std.echo
  base-input:
    output: "{$.str1}{$.str2}"
  input:
    - str1
    - str2
"""

ADHOC_ACTION_YAML_B = """
---
version: '2.0'

b_action:
  description: My super cool action.
  tags: ['test', 'v2']
  base: std.echo
  base-input:
    output: "{$.str1}{$.str2}"
  input:
    - str1
    - str2
"""

ADHOC_ACTION_YAML = """
---
version: '2.0'

my_action:
  description: My super cool action.
  tags: ['test', 'v2']
  base: std.echo
  base-input:
    output: "{$.str1}{$.str2}"
  input:
    - str1
    - str2
"""

ACTION_DEFINITION_INVALID_NO_BASE = """
---
version: '2.0'

my_action:
  description: My super cool action.
  tags: ['test', 'v2']

  base-input:
    output: "{$.str1}{$.str2}"
"""

ACTION_DEFINITION_INVALID_YAQL = """
---
version: '2.0'

my_action:
  description: My super cool action.
  tags: ['test', 'v2']
  base: std.echo
  base-input:
    output: <% $. %>
"""

ACTION_DSL_PARSE_EXCEPTION = """
---
%
"""

ACTION_SPEC = spec_parser.get_action_list_spec_from_yaml(ADHOC_ACTION_YAML)[0]

ACTION_DEF_VALUES = {
    'id': '123e4567-e89b-12d3-a456-426655440000',
    'name': 'my_action',
    'is_system': False,
    'description': 'My super cool action.',
    'tags': ['test', 'v2'],
    'definition': ADHOC_ACTION_YAML,
    'spec': ACTION_SPEC.to_dict(),
    'input': '',
    'project_id': None,
    'scope': 'public',
    'namespace': None
}


ACTION_DEF = models.ActionDefinition()
ACTION_DEF.update(ACTION_DEF_VALUES)

ACTION_DESC = adhoc.AdHocActionDescriptor(ACTION_DEF)


UPDATED_ADHOC_ACTION_YAML = """
---
version: '2.0'

my_action:
  description: My super cool action.
  base: std.echo
  base-input:
    output: "{$.str1}{$.str2}{$.str3}"
"""

UPDATED_ACTION_DEF = copy.copy(ACTION_DEF)
UPDATED_ACTION_DEF['definition'] = UPDATED_ADHOC_ACTION_YAML
UPDATED_ACTION = copy.deepcopy(ACTION_DEF_VALUES)
UPDATED_ACTION['definition'] = UPDATED_ADHOC_ACTION_YAML

MOCK_ACTIONS = mock.MagicMock(return_value=[ACTION_DEF])
MOCK_UPDATED_ACTION = mock.MagicMock(return_value=UPDATED_ACTION_DEF)


class TestActionsController(base.APITest):
    def check_adhoc_action_json(self, action_json):
        self.assertIsNotNone(action_json)
        self.assertIsInstance(action_json, dict)

        action_name = action_json['name']

        action_def = db_api.get_action_definition(action_name)

        self.assertIsNotNone(
            action_def,
            'Ad-hoc action definition does not exist [name=%s]' % action_name
        )

        # Compare action JSON with the state of the corresponding
        # persistent object.
        for k, v in action_json.items():
            self.assertEqual(v, utils.datetime_to_str(getattr(action_def, k)))

    def test_get(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        resp = self.app.get('/v2/actions/my_action')

        self.assertEqual(200, resp.status_int)

        self.check_adhoc_action_json(resp.json)

    @mock.patch.object(db_api, 'load_action_definition')
    def test_get_operational_error(self, mocked_get):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        action_def = db_api.get_action_definition('my_action')

        mocked_get.side_effect = [
            # Emulating DB OperationalError
            sa.exc.OperationalError('Mock', 'mock', 'mock'),
            action_def  # Successful run
        ]

        resp = self.app.get('/v2/actions/my_action')

        self.assertEqual(200, resp.status_int)

        self.check_adhoc_action_json(resp.json)

    def test_get_not_found(self):
        # This time we don't create an action in DB upfront.
        resp = self.app.get('/v2/actions/my_action', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    def test_get_by_id(self):
        # NOTE(rakhmerov): We can't support this case anymore because
        # action descriptors can now be identified only by names and
        # namespaces.
        pass

    def test_get_within_project_id(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        # We should not be able to change 'project_id' even with a
        # direct DB call.
        db_api.update_action_definition(
            'my_action',
            {'project_id': 'foobar'}
        )

        resp = self.app.get('/v2/actions/my_action')

        self.assertEqual(200, resp.status_int)
        self.assertEqual('<default-project>', resp.json['project_id'])

    def test_put(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        resp = self.app.put(
            '/v2/actions',
            UPDATED_ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)

        self.check_adhoc_action_json(resp.json['actions'][0])

    def test_put_public(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        resp = self.app.put(
            '/v2/actions?scope=public',
            UPDATED_ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'}
        )

        action_json = resp.json['actions'][0]

        self.assertEqual(200, resp.status_int)
        self.assertEqual('public', action_json['scope'])

        self.check_adhoc_action_json(action_json)

    def test_put_not_found(self):
        resp = self.app.put(
            '/v2/actions',
            UPDATED_ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    def test_put_system(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        db_api.update_action_definition('my_action', {'is_system': True})

        resp = self.app.put(
            '/v2/actions',
            ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            'Attempt to modify a system action: my_action',
            resp.body.decode()
        )

    def test_post(self):
        resp = self.app.post(
            '/v2/actions',
            ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)

        self.check_adhoc_action_json(resp.json['actions'][0])

    def test_post_public(self):
        resp = self.app.post(
            '/v2/actions?scope=public',
            ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(201, resp.status_int)

        self.check_adhoc_action_json(resp.json['actions'][0])
        self.assertEqual('public', resp.json['actions'][0]['scope'])

    def test_post_wrong_scope(self):
        resp = self.app.post(
            '/v2/actions?scope=unique',
            ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn("Scope must be one of the following", resp.body.decode())

    def test_post_dup(self):
        resp = self.app.post(
            '/v2/actions',
            ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(201, resp.status_int)

        # Try to create it again.
        resp = self.app.post(
            '/v2/actions',
            ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(409, resp.status_int)

    def test_delete(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        self.assertIsNotNone(db_api.load_action_definition('my_action'))

        resp = self.app.delete('/v2/actions/my_action')

        self.assertEqual(204, resp.status_int)

        self.assertIsNone(db_api.load_action_definition('my_action'))

    def test_delete_not_found(self):
        resp = self.app.delete('/v2/actions/my_action', expect_errors=True)

        self.assertEqual(404, resp.status_int)

    def test_get_all(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML_B)
        adhoc_actions.create_actions(ADHOC_ACTION_YAML_A)
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        resp = self.app.get('/v2/actions')

        self.assertEqual(200, resp.status_int)

        actions_json = resp.json['actions']

        # Verify they are sorted alphabetically
        self.assertEqual(actions_json[0]['name'], 'a_action')
        self.assertEqual(actions_json[1]['name'], 'b_action')
        self.assertEqual(actions_json[2]['name'], 'my_action')

        # There will be 'std.' actions and the one we've just created.
        self.assertGreater(len(actions_json), 1)

        # Let's check some of the well-known 'std.' actions.
        self._assert_single_item(actions_json, name='std.echo')
        self._assert_single_item(actions_json, name='std.ssh')
        self._assert_single_item(actions_json, name='std.fail')
        self._assert_single_item(actions_json, name='std.noop')
        self._assert_single_item(actions_json, name='std.async_noop')

        # Now let's check the ad-hoc action data.
        adhoc_action_json = self._assert_single_item(
            actions_json,
            name='my_action'
        )

        self.check_adhoc_action_json(adhoc_action_json)

    @mock.patch.object(db_api, 'get_action_definitions')
    def test_get_all_operational_error(self, mocked_get_all):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        action_def = db_api.get_action_definition('my_action')

        mocked_get_all.side_effect = [
            # Emulating DB OperationalError
            sa.exc.OperationalError('Mock', 'mock', 'mock'),
            [action_def]  # Successful run
        ]

        resp = self.app.get('/v2/actions')

        actions_json = resp.json['actions']

        # There will be 'std.' actions and the one we've just created.
        self.assertGreater(len(actions_json), 1)

        # Let's check some of the well-known 'std.' actions.
        self._assert_single_item(actions_json, name='std.echo')
        self._assert_single_item(actions_json, name='std.ssh')
        self._assert_single_item(actions_json, name='std.fail')
        self._assert_single_item(actions_json, name='std.noop')
        self._assert_single_item(actions_json, name='std.async_noop')

        # Now let's check the ad-hoc action data.
        adhoc_action_json = self._assert_single_item(
            actions_json,
            name='my_action'
        )

        self.check_adhoc_action_json(adhoc_action_json)

    @mock.patch.object(
        composite.CompositeActionProvider,
        'find_all',
        mock.MagicMock(return_value=[])
    )
    def test_get_all_empty(self):
        resp = self.app.get('/v2/actions')

        self.assertEqual(200, resp.status_int)

        self.assertEqual(0, len(resp.json['actions']))

    def test_get_all_filtered(self):
        # First check that w/o filters the result set
        # will contain more than 1 item.
        resp = self.app.get('/v2/actions')

        self.assertEqual(200, resp.status_int)
        self.assertGreater(len(resp.json['actions']), 1)

        # Now we'll filter it by action name.
        resp = self.app.get('/v2/actions?name=std.echo')

        self.assertEqual(200, resp.status_int)
        self.assertEqual(1, len(resp.json['actions']))

    def test_get_all_pagination(self):
        # Create an adhoc action for the purpose of the test.
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        resp = self.app.get(
            '/v2/actions?limit=1&sort_keys=created_at&sort_dirs=desc')

        self.assertEqual(200, resp.status_int)
        self.assertIn('next', resp.json)
        self.assertEqual(1, len(resp.json['actions']))

        self.check_adhoc_action_json(resp.json['actions'][0])

        param_dict = utils.get_dict_from_string(
            resp.json['next'].split('?')[1],
            delimiter='&'
        )

        action_def = db_api.get_action_definition('my_action')

        # TODO(rakhmerov): In this case we can't use IDs for marker because
        # in general we don't identify action descriptors with IDs.
        expected_dict = {
            'marker': action_def.id,
            'limit': 1,
            'sort_keys': 'created_at,id',
            'sort_dirs': 'desc,asc'
        }

        self.assertTrue(
            set(expected_dict.items()).issubset(set(param_dict.items()))
        )

    def test_get_all_sort_date_asc(self):
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)
        resp = self.app.get('/v2/actions?sort_keys=created_at&sort_dirs=asc')
        self.assertEqual(200, resp.status_int)

    def test_get_all_sort_date_desc(self):
        adhoc_actions.create_actions(ADHOC_ACTION_YAML_A)
        adhoc_actions.create_actions(ADHOC_ACTION_YAML_B)
        resp = self.app.get('/v2/actions?sort_keys=created_at&sort_dirs=desc')
        self.assertEqual(200, resp.status_int)

    def test_get_all_pagination_marker(self):
        adhoc_actions.create_actions(ADHOC_ACTION_YAML_B)
        adhoc_actions.create_actions(ADHOC_ACTION_YAML_A)
        adhoc_actions.create_actions(ADHOC_ACTION_YAML)

        resp = self.app.get('/v2/actions?limit=1')

        self.assertEqual(200, resp.status_int)
        self.assertEqual(1, len(resp.json['actions']))
        self.assertEqual(resp.json['actions'][0]['name'], 'a_action')

        resp = self.app.get('/v2/actions?marker=my_action&limit=2')

        self.assertEqual(200, resp.status_int)
        self.assertEqual(2, len(resp.json['actions']))
        self.assertEqual(resp.json['actions'][0]['name'], 'my_action')
        self.assertEqual(resp.json['actions'][1]['name'], 'std.async_noop')

    def test_get_all_pagination_limit_negative(self):
        resp = self.app.get(
            '/v2/actions?limit=-1&sort_keys=id,name&sort_dirs=asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("Limit must be positive", resp.body.decode())

    def test_get_all_pagination_limit_not_integer(self):
        resp = self.app.get(
            '/v2/actions?limit=1.1&sort_keys=id,name&sort_dirs=asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("unable to convert to int", resp.body.decode())

    def test_get_all_pagination_invalid_sort_dirs_length(self):
        resp = self.app.get(
            '/v2/actions?limit=1&sort_keys=id,name&sort_dirs=asc,asc,asc',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn(
            "Length of sort_keys must be equal or greater than sort_dirs",
            resp.body.decode()
        )

    def test_get_all_pagination_unknown_direction(self):
        resp = self.app.get(
            '/v2/actions?limit=1&sort_keys=id&sort_dirs=nonexist',
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)

        self.assertIn("Unknown sort direction", resp.body.decode())

    def test_validate(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ADHOC_ACTION_YAML,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)
        self.assertTrue(resp.json['valid'])

    def test_validate_invalid_model_exception(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ACTION_DEFINITION_INVALID_NO_BASE,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])

    def test_validate_dsl_parse_exception(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ACTION_DSL_PARSE_EXCEPTION,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Definition could not be parsed", resp.json['error'])

    def test_validate_yaql_parse_exception(self):
        resp = self.app.post(
            '/v2/actions/validate',
            ACTION_DEFINITION_INVALID_YAQL,
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("unexpected end of statement",
                      resp.json['error'])

    def test_validate_empty(self):
        resp = self.app.post(
            '/v2/actions/validate',
            '',
            headers={'Content-Type': 'text/plain'},
            expect_errors=True
        )

        self.assertEqual(200, resp.status_int)
        self.assertFalse(resp.json['valid'])
        self.assertIn("Invalid DSL", resp.json['error'])
