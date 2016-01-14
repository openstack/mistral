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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import actions as action_service
from mistral.tests.unit import base
from mistral import utils
from mistral.workbook import parser as spec_parser


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


ACTION_LIST = """
---
version: '2.0'

action1:
  tags: [test, v2]
  base: std.echo output='Hi'
  output:
    result: $

action2:
  base: std.echo output='Hey'
  output:
    result: $
"""

UPDATED_ACTION_LIST = """
---
version: '2.0'

action1:
  base: std.echo output='Hi'
  input:
    - param1
  output:
    result: $
"""


class ActionServiceTest(base.DbTestCase):
    def setUp(self):
        super(ActionServiceTest, self).setUp()

        self.addCleanup(db_api.delete_action_definitions, name='action1')
        self.addCleanup(db_api.delete_action_definitions, name='action2')

    def test_create_actions(self):
        db_actions = action_service.create_actions(ACTION_LIST)

        self.assertEqual(2, len(db_actions))

        # Action 1.
        action1_db = self._assert_single_item(db_actions, name='action1')
        action1_spec = spec_parser.get_action_spec(action1_db.spec)

        self.assertEqual('action1', action1_spec.get_name())
        self.assertListEqual(['test', 'v2'], action1_spec.get_tags())
        self.assertEqual('std.echo', action1_spec.get_base())
        self.assertDictEqual({'output': 'Hi'}, action1_spec.get_base_input())

        # Action 2.
        action2_db = self._assert_single_item(db_actions, name='action2')
        action2_spec = spec_parser.get_action_spec(action2_db.spec)

        self.assertEqual('action2', action2_spec.get_name())
        self.assertEqual('std.echo', action1_spec.get_base())
        self.assertDictEqual({'output': 'Hey'}, action2_spec.get_base_input())

    def test_update_actions(self):
        db_actions = action_service.create_actions(ACTION_LIST)

        self.assertEqual(2, len(db_actions))

        action1_db = self._assert_single_item(db_actions, name='action1')
        action1_spec = spec_parser.get_action_spec(action1_db.spec)

        self.assertEqual('action1', action1_spec.get_name())
        self.assertEqual('std.echo', action1_spec.get_base())
        self.assertDictEqual({'output': 'Hi'}, action1_spec.get_base_input())
        self.assertDictEqual({}, action1_spec.get_input())

        db_actions = action_service.update_actions(UPDATED_ACTION_LIST)

        # Action 1.
        action1_db = self._assert_single_item(db_actions, name='action1')
        action1_spec = spec_parser.get_action_spec(action1_db.spec)

        self.assertEqual('action1', action1_spec.get_name())
        self.assertListEqual([], action1_spec.get_tags())
        self.assertEqual('std.echo', action1_spec.get_base())
        self.assertDictEqual({'output': 'Hi'}, action1_spec.get_base_input())
        self.assertIn('param1', action1_spec.get_input())
        self.assertIs(
            action1_spec.get_input().get('param1'),
            utils.NotDefined
        )
