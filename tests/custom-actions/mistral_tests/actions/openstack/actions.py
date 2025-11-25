# Copyright 2014 - Mirantis, Inc.
# Modified in 2025 by NetCracker Technology Corp.
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


from mistral_tests.actions.openstack import base, test_actions
from mistral_tests.actions.openstack.action_generator.base import get_mapping
from mistral_tests.actions.openstack.action_generator.base import \
    OpenStackActionGenerator
from oslo_config import cfg
from oslo_log import log
from oslo_utils import importutils

LOG = log.getLogger(__name__)

CONF = cfg.CONF

IRONIC_API_VERSION = '1.34'
"""The default microversion to pass to Ironic API.

1.34 corresponds to Pike final.
"""


def _try_import(module_name):
    try:
        return importutils.try_import(module_name)
    except Exception as e:
        msg = 'Unable to load module "%s". %s' % (module_name, str(e))
        LOG.error(msg)
        return None


novaclient = _try_import('novaclient.client')


class NovaAction(base.OpenStackAction, OpenStackActionGenerator):
    _service_type = 'compute'

    @classmethod
    def _get_client_class(cls):
        return novaclient.Client

    def _create_client(self, context):
        LOG.debug("Nova action security context: %s", context)

        return novaclient.Client(2, **self.get_session_and_auth(context))

    def _create_test_client(self, context):
        return test_actions.NovaTestClient()

    @classmethod
    def _get_fake_client(cls):
        return cls._get_client_class()(2)

    @classmethod
    def get_base_action_class(cls):
        return NovaAction

    @classmethod
    def get_action_namespace(cls):
        return 'test_nova'

    @classmethod
    def get_mapping(cls):
        return get_mapping()[cls.get_action_namespace()]
