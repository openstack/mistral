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

"""
This module is a facade for all action subsystem. It represents a
collection of functions for accessing information about actions
available in the system.
"""

from oslo_log import log as logging
from stevedore import extension

from mistral_lib import actions as ml_actions

from mistral.actions import test

LOG = logging.getLogger(__name__)

_SYSTEM_PROVIDER = None
_TEST_PROVIDER = None


def _get_registered_providers():
    providers = []

    mgr = extension.ExtensionManager(
        namespace='mistral.action.providers',
        invoke_on_load=False
    )

    for provider_name in mgr.names():
        provider_cls = mgr[provider_name].plugin

        try:
            providers.append(provider_cls(provider_name))
        except Exception:
            LOG.exception(
                'Failed to instantiate an action provider from the class: %s',
                provider_cls
            )

            raise

    if not providers:
        LOG.warning("No action providers found in the system.")

    return providers


def get_test_action_provider():
    """Returns a singleton for the test action provider."""

    global _TEST_PROVIDER

    if _TEST_PROVIDER is None:
        _TEST_PROVIDER = test.TestActionProvider()

    return _TEST_PROVIDER


def get_system_action_provider():
    """Returns a singleton for the system action provider.

    In fact, this method serves a facade for the entire action subsystem.
    Clients of the acton subsystem must get the system action provider
    and work with actions through it. The system action provider created
    by this method (on the first call) is nothing but just a composite
    on top of the action providers registered in the entry point
    "mistral.action.providers".
    """

    global _SYSTEM_PROVIDER

    if _SYSTEM_PROVIDER is None:
        delegates = _get_registered_providers()

        # Add an action provider for testing to the end of the list
        # so that it has the lowest priority. In production runs it's
        # always empty so it won't take any effect.
        delegates.append(get_test_action_provider())

        _SYSTEM_PROVIDER = ml_actions.CompositeActionProvider(
            'system',
            delegates
        )

    return _SYSTEM_PROVIDER
