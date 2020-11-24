# Copyright 2020 - Nokia Software.
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

from mistral.db.v2 import api as db_api
from mistral.services import actions
from mistral.tests.unit.api import base


TEST_MODULE_TEXT = """
from mistral_lib import actions

class DummyAction(actions.Action):
    def run(self, context):
        return "Hello from the dummy action 1!"

    def test(self, context):
        return None

class DummyAction2(actions.Action):
    def run(self, context):
        return "Hello from the dummy action 2!"

    def test(self, context):
        return None"""


class TestDynamicActionsController(base.APITest):
    def setUp(self):
        super(TestDynamicActionsController, self).setUp()

        resp = self.app.post(
            '/v2/code_sources?name=test_dummy_module',
            TEST_MODULE_TEXT
        )

        self.code_source_id = resp.json['id']

        self.addCleanup(db_api.delete_code_sources)
        self.addCleanup(db_api.delete_dynamic_action_definitions)

    def _create_dynamic_action(self):
        return self.app.post_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'DummyAction',
                'code_source_id': self.code_source_id
            }
        )

    def test_post(self):
        resp = self.app.post_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'DummyAction',
                'code_source_id': self.code_source_id
            }
        )

        # Check the structure of the response.
        self.assertEqual(201, resp.status_int)

        dyn_action = resp.json

        self.assertEqual('dummy_action', dyn_action['name'])
        self.assertEqual('DummyAction', dyn_action['class_name'])
        self.assertEqual(self.code_source_id, dyn_action['code_source_id'])

        # Make sure the action can be found via the system action provider
        # and it's fully functioning.
        provider = actions.get_system_action_provider()

        action_desc = provider.find('dummy_action')

        self.assertIsNotNone(action_desc)

        action = action_desc.instantiate({}, None)

        self.assertIsNotNone(action)

        self.assertEqual("Hello from the dummy action 1!", action.run(None))

    def test_put(self):
        resp = self._create_dynamic_action()

        self.assertEqual(201, resp.status_int)

        resp = self.app.put_json(
            '/v2/dynamic_actions',
            {
                'name': 'dummy_action',
                'class_name': 'NewDummyAction'
            }
        )

        self.assertEqual(200, resp.status_int)

        dyn_action = resp.json

        self.assertEqual('dummy_action', dyn_action['name'])
        self.assertEqual('NewDummyAction', dyn_action['class_name'])

    def test_get(self):
        self._create_dynamic_action()

        resp = self.app.get('/v2/dynamic_actions/dummy_action')

        self.assertEqual(200, resp.status_int)

        dyn_action = resp.json

        self.assertEqual('dummy_action', dyn_action['name'])
        self.assertEqual('DummyAction', dyn_action['class_name'])
        self.assertEqual(self.code_source_id, dyn_action['code_source_id'])
        self.assertEqual('test_dummy_module', dyn_action['code_source_name'])

    def test_get_all(self):
        self._create_dynamic_action()

        resp = self.app.get('/v2/dynamic_actions')

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        dynamic_actions = resp_json.get('dynamic_actions')

        self.assertEqual(1, len(dynamic_actions))

    def test_delete(self):
        resp = self._create_dynamic_action()

        # Check the structure of the response
        self.assertEqual(201, resp.status_int)

        resp = self.app.get('/v2/dynamic_actions/dummy_action')

        self.assertEqual(200, resp.status_int)

        self.app.delete('/v2/dynamic_actions/dummy_action')

        resp = self.app.get(
            '/v2/dynamic_actions/dummy_action',
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

        # Make sure the system action provider doesn't find an action
        # descriptor for the action.
        provider = actions.get_system_action_provider()

        self.assertIsNone(provider.find('dummy_action'))
