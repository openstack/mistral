# Copyright 2025 Binero.
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

from mistral import config
from mistral.services.actions import _get_registered_providers
from mistral.tests.unit import base


class FakeExtManager:
    def __init__(self):
        self.plugins = ['adhoc', 'dynamic', 'legacy']

    def names(self):
        return self.plugins


class ActionsTest(base.DbTestCase):
    def setUp(self):
        super(ActionsTest, self).setUp()

    @mock.patch('stevedore.enabled.ExtensionManager')
    def test_get_registered_providers(self, mock_ext_mgr):
        mock_ext_mgr.return_value = FakeExtManager()
        providers = _get_registered_providers()
        self.assertEqual(3, len(providers))
        self.assertEqual('adhoc', providers[0].name)
        self.assertEqual('dynamic', providers[1].name)
        self.assertEqual('legacy', providers[2].name)

    @mock.patch('stevedore.enabled.ExtensionManager')
    def test_get_registered_providers_allowlist(self, mock_ext_mgr):
        self.override_config(
            'allowlist', ['dynamic'], config.ACTION_PROVIDERS_GROUP)
        mock_ext_mgr.return_value = FakeExtManager()
        providers = _get_registered_providers()
        self.assertEqual(1, len(providers))
        self.assertEqual('dynamic', providers[0].name)

    @mock.patch('stevedore.enabled.ExtensionManager')
    def test_get_registered_providers_allowlist_fnmatch(self, mock_ext_mgr):
        self.override_config(
            'allowlist', ['ad*'], config.ACTION_PROVIDERS_GROUP)
        mock_ext_mgr.return_value = FakeExtManager()
        providers = _get_registered_providers()
        self.assertEqual(1, len(providers))
        self.assertEqual('adhoc', providers[0].name)

    @mock.patch('stevedore.enabled.ExtensionManager')
    def test_get_registered_providers_denylist(self, mock_ext_mgr):
        self.override_config(
            'denylist', ['legacy'], config.ACTION_PROVIDERS_GROUP)
        mock_ext_mgr.return_value = FakeExtManager()
        providers = _get_registered_providers()
        self.assertEqual(2, len(providers))
        self.assertEqual('adhoc', providers[0].name)
        self.assertEqual('dynamic', providers[1].name)

    @mock.patch('stevedore.enabled.ExtensionManager')
    def test_get_registered_providers_denylist_fnmatch(self, mock_ext_mgr):
        self.override_config(
            'denylist', ['leg*'], config.ACTION_PROVIDERS_GROUP)
        mock_ext_mgr.return_value = FakeExtManager()
        providers = _get_registered_providers()
        self.assertEqual(2, len(providers))
        self.assertEqual('adhoc', providers[0].name)
        self.assertEqual('dynamic', providers[1].name)

    @mock.patch('stevedore.enabled.ExtensionManager')
    def test_get_registered_providers_allow_and_deny(self, mock_ext_mgr):
        self.override_config(
            'allowlist', ['adhoc'], group=config.ACTION_PROVIDERS_GROUP)
        self.override_config(
            'denylist', ['dynamic'], group=config.ACTION_PROVIDERS_GROUP)
        mock_ext_mgr.return_value = FakeExtManager()
        providers = _get_registered_providers()
        self.assertEqual(1, len(providers))
        self.assertEqual('adhoc', providers[0].name)
