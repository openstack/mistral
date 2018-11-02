# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mistral.rpc.kombu import kombu_hosts
from mistral.tests.unit import base
from oslo_config import cfg

import functools
import oslo_messaging


HOST_1 = 'rabbitmq_1'
PORT_1 = 5671
HOST_2 = 'rabbitmq_2'
PORT_2 = 5672
USER_1 = 'u_mistral_1'
PASSWORD_1 = 'p_mistral_1'
USER_2 = 'u_mistral_2'
PASSWORD_2 = 'p_mistral_2'
VIRTUAL_HOST_1 = 'vhost_1'
VIRTUAL_HOST_2 = 'vhost_2'


class KombuHostsTestCase(base.BaseTest):

    def setUp(self):
        super(KombuHostsTestCase, self).setUp()

        # Oslo messaging set a default config option
        oslo_messaging.get_transport(cfg.CONF)

    def assert_transports_host(self, expected, result):
        sorted_by_host = functools.partial(sorted, key=lambda x: x.hostname)

        self.assertListEqual(sorted_by_host(expected), sorted_by_host(result))

    def test_transport_url(self):
        self.override_config(
            'transport_url',
            'rabbit://{user}:{password}@{host}:{port}/{virtual_host}'.format(
                user=USER_1, port=PORT_1, host=HOST_1,
                password=PASSWORD_1,
                virtual_host=VIRTUAL_HOST_1
            ))

        hosts = kombu_hosts.KombuHosts(cfg.CONF)

        self.assertEqual(VIRTUAL_HOST_1, hosts.virtual_host)
        self.assert_transports_host([oslo_messaging.TransportHost(
            hostname=HOST_1,
            port=PORT_1,
            username=USER_1,
            password=PASSWORD_1,
        )], hosts.hosts)

    def test_transport_url_multiple_hosts(self):
        self.override_config(
            'transport_url',
            'rabbit://{user_1}:{password_1}@{host_1}:{port_1},'
            '{user_2}:{password_2}@{host_2}:{port_2}/{virtual_host}'.format(
                user_1=USER_1,
                password_1=PASSWORD_1,
                port_1=PORT_1,
                host_1=HOST_1,
                user_2=USER_2,
                password_2=PASSWORD_2,
                host_2=HOST_2,
                port_2=PORT_2,
                virtual_host=VIRTUAL_HOST_1
            ))

        hosts = kombu_hosts.KombuHosts(cfg.CONF)

        self.assertEqual(VIRTUAL_HOST_1, hosts.virtual_host)
        self.assert_transports_host(
            [
                oslo_messaging.TransportHost(
                    hostname=HOST_1,
                    port=PORT_1,
                    username=USER_1,
                    password=PASSWORD_1
                ),
                oslo_messaging.TransportHost(
                    hostname=HOST_2,
                    port=PORT_2,
                    username=USER_2,
                    password=PASSWORD_2
                )
            ],
            hosts.hosts
        )
