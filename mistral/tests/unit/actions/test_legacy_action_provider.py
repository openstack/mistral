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

from unittest import mock

from mistral_lib import actions as ml_actions
from mistral_lib.utils import inspect_utils

from mistral.actions import legacy
from mistral.tests.unit import base


class BuildMessageAction(ml_actions.Action):
    msg_pattern = '%s'

    def __init__(self, name):
        super(BuildMessageAction, self).__init__()

        self._name = name

    def run(self, context):
        return self.msg_pattern % self._name


class TestActionGenerator(object):
    base_action_class = BuildMessageAction

    @classmethod
    def create_actions(cls):
        action_dicts = []

        hello_action_cls = type(
            'HelloAction',
            (BuildMessageAction,),
            {'msg_pattern': 'Hello, %s!'}
        )

        action_dicts.append(
            {
                'class': hello_action_cls,
                'name': 'hello',
                'description': 'The action builds a hello message',
                'arg_list': inspect_utils.get_arg_list_as_str(
                    hello_action_cls.__init__
                )
            }
        )

        goodbye_action_cls = type(
            'GoodbyeAction',
            (BuildMessageAction,),
            {'msg_pattern': 'Goodbye, %s!'}
        )

        action_dicts.append(
            {
                'class': goodbye_action_cls,
                'name': 'goodbye',
                'description': 'The action builds a goodbye message',
                'arg_list': inspect_utils.get_arg_list_as_str(
                    goodbye_action_cls.__init__
                )
            }
        )

        return action_dicts


class LegacyActionProviderTest(base.BaseTest):
    def test_only_builtin_actions(self):
        self.override_config(
            'load_action_generators',
            False,
            'legacy_action_provider'
        )
        self.override_config(
            'only_builtin_actions',
            True,
            'legacy_action_provider'
        )

        provider = legacy.LegacyActionProvider()

        # Test find_all() method.
        action_descs = provider.find_all()

        self.assertTrue(len(action_descs) > 0)

        self.assertTrue(
            all(
                [
                    a_d.action_class.__module__.startswith('mistral.')
                    for a_d in action_descs
                ]
            )
        )

        self._assert_single_item(action_descs, name='std.echo')

        # Test find() method.
        action_desc = provider.find('std.echo')

        self.assertIsNotNone(action_desc)
        self.assertEqual('std.echo', action_desc.name)
        self.assertIn('Echo action.', action_desc.description)
        self.assertEqual(
            'mistral.actions.std_actions.EchoAction',
            action_desc.action_class_name
        )
        self.assertEqual('output, delay=0', action_desc.params_spec)

    @mock.patch.object(
        legacy.LegacyActionProvider,
        '_get_action_generators',
        mock.MagicMock(return_value=[TestActionGenerator])
    )
    def test_only_action_plugins(self):
        self.override_config(
            'load_action_generators',
            False,
            'legacy_action_provider'
        )

        provider = legacy.LegacyActionProvider()

        action_descs = provider.find_all()

        prefix = 'mistral.actions.std_actions'

        self.assertTrue(
            all(
                [
                    a_d.action_class.__module__ == prefix
                    for a_d in action_descs
                ]
            )
        )

        self._assert_single_item(action_descs, name='std.echo')

    @mock.patch.object(
        legacy.LegacyActionProvider,
        '_get_action_generators',
        mock.MagicMock(return_value=[TestActionGenerator])
    )
    def test_only_action_generators(self):
        self.override_config(
            'load_action_generators',
            True,
            'legacy_action_provider'
        )
        self.override_config(
            'load_action_plugins',
            False,
            'legacy_action_provider'
        )

        provider = legacy.LegacyActionProvider()

        action_descs = provider.find_all()

        self.assertEqual(2, len(action_descs))

        hello_action_desc = self._assert_single_item(
            action_descs,
            name='hello',
            params_spec='name',
            description='The action builds a hello message',
            action_class_name='mistral.tests.unit.actions.'
                              'test_legacy_action_provider.BuildMessageAction',
            action_class_attributes={'msg_pattern': 'Hello, %s!'}
        )

        hello_action = hello_action_desc.instantiate({'name': 'Forest'}, {})

        self.assertEqual('Hello, Forest!', hello_action.run(None))

        goodbye_action_desc = self._assert_single_item(
            action_descs,
            name='goodbye',
            params_spec='name',
            description='The action builds a goodbye message',
            action_class_name='mistral.tests.unit.actions.'
                              'test_legacy_action_provider.BuildMessageAction',
            action_class_attributes={'msg_pattern': 'Goodbye, %s!'}
        )

        goodbye_action = goodbye_action_desc.instantiate(
            {'name': 'Lieutenant Dan'},
            {}
        )

        self.assertEqual('Goodbye, Lieutenant Dan!', goodbye_action.run(None))
