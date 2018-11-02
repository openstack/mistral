# Copyright (c) 2016 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from mistral import config as cfg
from mistral.rpc.kombu import base as kombu_base
from mistral.tests.unit import base


class KombuTestCase(base.BaseTest):

    def setUp(self):
        super(KombuTestCase, self).setUp()

        kombu_base.set_transport_options(check_backend=False)

        cfg.CONF.set_default('transport_url', 'rabbit://localhost:567')
