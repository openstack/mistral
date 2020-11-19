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

CREATE_REQUEST = """
-
  name: dummy_action
  class_name: DummyAction
  code_source_id: {}
"""

UPDATE_REQUEST = """
dummy_action:
  class_name: NewDummyAction
  code_source_id: {}
"""


class TestDynamicActionsController(base.APITest):
    def setUp(self):
        super(TestDynamicActionsController, self).setUp()

        resp = self._create_code_source().json

        self.code_source_id = resp.get('code_sources')[0].get('id')

        self.addCleanup(self._delete_code_source)

    def _create_code_source(self):
        return self.app.post(
            '/v2/code_sources',
            upload_files=[
                ('test_dummy_module', 'filename', TEST_MODULE_TEXT.encode())
            ],
        )

    def _create_dynamic_action(self, body):
        return self.app.post(
            '/v2/dynamic_actions',
            body,
            content_type="text/plain"
        )

    def _delete_code_source(self):
        return self.app.delete('/v2/code_sources/test_dummy_module')

    def test_create_dynamic_action(self):
        resp = self._create_dynamic_action(
            CREATE_REQUEST.format(self.code_source_id)
        )

        # Check the structure of the response.
        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        dynamic_actions = resp_json.get('dynamic_actions')

        self.assertEqual(1, len(dynamic_actions))

        dynamic_action = dynamic_actions[0]

        self.assertEqual('dummy_action', dynamic_action.get('name'))
        self.assertEqual('DummyAction', dynamic_action.get('class_name'))
        self.assertEqual(
            self.code_source_id,
            dynamic_action.get('code_source_id')
        )

        # Make sure the action can be found via the system action provider
        # and it's fully functioning.
        provider = actions.get_system_action_provider()

        action_desc = provider.find('dummy_action')

        self.assertIsNotNone(action_desc)

        action = action_desc.instantiate({}, None)

        self.assertIsNotNone(action)

        self.assertEqual("Hello from the dummy action 1!", action.run(None))

        # Delete the action
        self.app.delete('/v2/dynamic_actions/dummy_action')

    def test_update_dynamic_action(self):
        self._create_dynamic_action(
            CREATE_REQUEST.format(self.code_source_id)
        )

        resp = self.app.put(
            '/v2/dynamic_actions',
            UPDATE_REQUEST.format(self.code_source_id),
            content_type="text/plain"
        )

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        dynamic_actions = resp_json.get('dynamic_actions')

        self.assertEqual(1, len(dynamic_actions))

        dynamic_action = dynamic_actions[0]

        self.assertEqual('dummy_action', dynamic_action.get('name'))
        self.assertEqual('NewDummyAction', dynamic_action.get('class_name'))
        self.assertEqual(
            self.code_source_id,
            dynamic_action.get('code_source_id')
        )

        self.app.delete('/v2/dynamic_actions/dummy_action')

    def test_get_dynamic_action(self):
        resp = self._create_dynamic_action(
            CREATE_REQUEST.format(self.code_source_id)
        )

        self.assertEqual(200, resp.status_int)

        self.app.delete('/v2/dynamic_actions/dummy_action')

    def test_get_all_dynamic_actions(self):
        self._create_dynamic_action(
            CREATE_REQUEST.format(self.code_source_id)
        )

        resp = self.app.get('/v2/dynamic_actions')

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        dynamic_actions = resp_json.get('dynamic_actions')

        self.assertEqual(1, len(dynamic_actions))

        self.app.delete('/v2/dynamic_actions/dummy_action')

    def test_delete_dynamic_action(self):
        resp = self._create_dynamic_action(
            CREATE_REQUEST.format(self.code_source_id)
        )

        # Check the structure of the response
        self.assertEqual(200, resp.status_int)

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
