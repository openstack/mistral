# Copyright 2015 - Mirantis, Inc.
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

from mistral.tests.unit.engine import base
from mistral.utils import rpc_utils


class RPCTest(base.EngineTestCase):
    def setUp(self):
        super(RPCTest, self).setUp()

    def test_get_rabbit_config(self):
        conf = cfg.CONF

        rpc_info = rpc_utils._get_rabbit_info_from_oslo(conf.engine)

        self.assertDictEqual(
            {
                'topic': 'mistral_engine',
                'port': 5672,
                'server_id': '0.0.0.0',
                'user_id': 'guest',
                'virtual_host': '/',
                'host': 'localhost',
                'exchange': 'openstack',
                'password': 'guest',
                'durable_queues': False,
                'auto_delete': False
            },
            rpc_info
        )
