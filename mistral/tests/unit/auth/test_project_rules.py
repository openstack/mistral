# Copyright 2026 - NetCracker Technology Corp.
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

import json
from unittest import mock

from oslotest import base

from mistral.auth import project_rules


class TestResolveFieldValue(base.BaseTestCase):

    def test_simple_field(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        self.assertEqual(
            'http://idp/auth/realms/cloud-common',
            project_rules._resolve_field_value(token, 'iss')
        )

    def test_missing_field_returns_none(self):
        self.assertIsNone(project_rules._resolve_field_value({}, 'iss'))

    def test_index_notation_list(self):
        token = {'aud': ['account', 'other']}
        self.assertEqual(
            'account',
            project_rules._resolve_field_value(token, 'aud[0]')
        )
        self.assertEqual(
            'other',
            project_rules._resolve_field_value(token, 'aud[1]')
        )

    def test_index_notation_out_of_range(self):
        token = {'aud': ['account']}
        self.assertIsNone(project_rules._resolve_field_value(token, 'aud[5]'))

    def test_index_notation_not_a_list(self):
        token = {'aud': 'account'}
        self.assertIsNone(project_rules._resolve_field_value(token, 'aud[0]'))

    def test_string_aud_without_index(self):
        token = {'aud': 'account'}
        self.assertEqual(
            'account',
            project_rules._resolve_field_value(token, 'aud')
        )


class TestExtractRule(base.BaseTestCase):

    def _resolve(self, token, rules):
        return project_rules.resolve_project_id(token, rules)

    def test_extract_from_iss(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        rules = [{'type': 'extract', 'field': 'iss',
                  'pattern': '*/realms/{value}'}]
        self.assertEqual('cloud-common', self._resolve(token, rules))

    def test_extract_no_match_returns_none(self):
        token = {'iss': 'http://idp/no-realms-here'}
        rules = [{'type': 'extract', 'field': 'iss',
                  'pattern': '*/realms/{value}'}]
        self.assertIsNone(self._resolve(token, rules))

    def test_extract_missing_pattern_skipped(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        rules = [{'type': 'extract', 'field': 'iss'}]
        self.assertIsNone(self._resolve(token, rules))

    def test_extract_missing_field_in_token_skipped(self):
        token = {}
        rules = [{'type': 'extract', 'field': 'iss',
                  'pattern': '*/realms/{value}'}]
        self.assertIsNone(self._resolve(token, rules))

    def test_extract_missing_field_key_in_rule_skipped(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        rules = [{'type': 'extract', 'pattern': '*/realms/{value}'}]
        self.assertIsNone(self._resolve(token, rules))


class TestMapRule(base.BaseTestCase):

    def _resolve(self, token, rules):
        return project_rules.resolve_project_id(token, rules)

    def test_map_with_pattern_matches(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        rules = [{'type': 'map', 'field': 'iss',
                  'pattern': '*/realms/{value}',
                  'value': 'cloud-common', 'project': 'my-project'}]
        self.assertEqual('my-project', self._resolve(token, rules))

    def test_map_with_pattern_no_match(self):
        token = {'iss': 'http://idp/auth/realms/other-realm'}
        rules = [{'type': 'map', 'field': 'iss',
                  'pattern': '*/realms/{value}',
                  'value': 'cloud-common', 'project': 'my-project'}]
        self.assertIsNone(self._resolve(token, rules))

    def test_map_without_pattern_matches(self):
        token = {'aud': 'account'}
        rules = [{'type': 'map', 'field': 'aud',
                  'value': 'account', 'project': 'my-project'}]
        self.assertEqual('my-project', self._resolve(token, rules))

    def test_map_without_pattern_no_match(self):
        token = {'aud': 'other'}
        rules = [{'type': 'map', 'field': 'aud',
                  'value': 'account', 'project': 'my-project'}]
        self.assertIsNone(self._resolve(token, rules))

    def test_map_with_list_aud_index(self):
        token = {'aud': ['account', 'other']}
        rules = [{'type': 'map', 'field': 'aud[0]',
                  'value': 'account', 'project': 'my-project'}]
        self.assertEqual('my-project', self._resolve(token, rules))

    def test_map_missing_value_skipped(self):
        token = {'aud': 'account'}
        rules = [{'type': 'map', 'field': 'aud', 'project': 'my-project'}]
        self.assertIsNone(self._resolve(token, rules))

    def test_map_missing_project_skipped(self):
        token = {'aud': 'account'}
        rules = [{'type': 'map', 'field': 'aud', 'value': 'account'}]
        self.assertIsNone(self._resolve(token, rules))


class TestMultipleRules(base.BaseTestCase):

    def _resolve(self, token, rules):
        return project_rules.resolve_project_id(token, rules)

    def test_first_matching_rule_wins(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common', 'aud': 'account'}
        rules = [
            {'type': 'map', 'field': 'aud',
             'value': 'account', 'project': 'first-match'},
            {'type': 'extract', 'field': 'iss',
             'pattern': '*/realms/{value}'},
        ]
        self.assertEqual('first-match', self._resolve(token, rules))

    def test_falls_through_to_second_rule(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common', 'aud': 'other'}
        rules = [
            {'type': 'map', 'field': 'aud',
             'value': 'account', 'project': 'first-match'},
            {'type': 'extract', 'field': 'iss',
             'pattern': '*/realms/{value}'},
        ]
        self.assertEqual('cloud-common', self._resolve(token, rules))

    def test_no_rules_returns_none(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        self.assertIsNone(self._resolve(token, []))

    def test_unknown_rule_type_skipped(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        rules = [{'type': 'unknown', 'field': 'iss'}]
        self.assertIsNone(self._resolve(token, rules))


class TestResolveFromConfig(base.BaseTestCase):

    def test_no_config_returns_none(self):
        with mock.patch('mistral.auth.project_rules.CONF') as mock_conf:
            mock_conf.auth.project_rules = None
            self.assertIsNone(
                project_rules.resolve_project_id_from_config({})
            )

    def test_empty_config_returns_none(self):
        with mock.patch('mistral.auth.project_rules.CONF') as mock_conf:
            mock_conf.auth.project_rules = ''
            self.assertIsNone(
                project_rules.resolve_project_id_from_config({})
            )

    def test_invalid_json_returns_none(self):
        with mock.patch('mistral.auth.project_rules.CONF') as mock_conf:
            mock_conf.auth.project_rules = 'not-json'
            self.assertIsNone(
                project_rules.resolve_project_id_from_config({})
            )

    def test_valid_config_resolves(self):
        token = {'iss': 'http://idp/auth/realms/cloud-common'}
        rules = [{'type': 'extract', 'field': 'iss',
                  'pattern': '*/realms/{value}'}]
        with mock.patch('mistral.auth.project_rules.CONF') as mock_conf:
            mock_conf.auth.project_rules = json.dumps(rules)
            self.assertEqual(
                'cloud-common',
                project_rules.resolve_project_id_from_config(token)
            )

    def test_no_match_returns_none(self):
        token = {'iss': 'http://idp/no-realms'}
        rules = [{'type': 'extract', 'field': 'iss',
                  'pattern': '*/realms/{value}'}]
        with mock.patch('mistral.auth.project_rules.CONF') as mock_conf:
            mock_conf.auth.project_rules = json.dumps(rules)
            self.assertIsNone(
                project_rules.resolve_project_id_from_config(token)
            )
