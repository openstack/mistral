# Copyright 2020 Nokia Software.
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

from mistral.actions import dynamic_action
from mistral.services import code_sources as code_sources_service
from mistral.services import dynamic_actions as dynamic_actions_service
from mistral.tests.unit import base

DUMMY_CODE_SOURCE = """from mistral_lib import actions

class DummyAction(actions.Action):
    def run(self, context):
        return None
    def test(self, context):
        return None
class DummyAction2(actions.Action):
    def run(self, context):
        return None
    def test(self, context):
        return None
"""

ACTIONS = []
NAMESPACE = "ns"


class DynamicActionProviderTest(base.DbTestCase):

    def _create_code_source(self, namespace=''):
        return code_sources_service.create_code_source(
            name='code_source',
            src_code=DUMMY_CODE_SOURCE,
            namespace=namespace
        )

    def _delete_code_source(self):
        return code_sources_service.delete_code_source(
            identifier='code_source',
        )

    def _create_dynamic_actions(self, code_source_id, namespace=''):
        actions = [
            {
                "name": "dummy_action",
                "class_name": "DummyAction",
                "code_source_id": code_source_id
            },
            {
                "name": "dummy_action2",
                "class_name": "DummyAction2",
                "code_source_id": code_source_id
            }]

        dynamic_actions_service.create_dynamic_actions(
            actions,
            namespace=namespace
        )

    def test_Dynamic_actions(self):
        provider = dynamic_action.DynamicActionProvider()

        action_descs = provider.find_all()

        self.assertEqual(0, len(action_descs))

        code_source = self._create_code_source()
        self._create_dynamic_actions(code_source_id=code_source['id'])

        action_descs = provider.find_all()

        self.assertEqual(2, len(action_descs))

        self._delete_code_source()

    def test_loaded_actions_deleted_from_db(self):
        provider = dynamic_action.DynamicActionProvider()

        action_descs = provider.find_all()

        self.assertEqual(0, len(action_descs))

        code_source = self._create_code_source()
        self._create_dynamic_actions(code_source_id=code_source['id'])

        action_descs = provider.find_all()

        self.assertEqual(2, len(action_descs))

        self._delete_code_source()

        action_descs = provider.find_all()

        self.assertEqual(0, len(action_descs))

    def test_Dynamic_actions_with_namespace(self):
        provider = dynamic_action.DynamicActionProvider()

        action_descs = provider.find_all()

        self.assertEqual(0, len(action_descs))

        code_source = self._create_code_source()
        self._create_dynamic_actions(
            code_source_id=code_source['id'],
            namespace=NAMESPACE
        )
        action_descs = provider.find_all(namespace=NAMESPACE)

        self.assertEqual(2, len(action_descs))

        action_descs = provider.find_all(namespace='')

        self.assertEqual(0, len(action_descs))

        self._delete_code_source()
