# Copyright 2015 Huawei Technologies Co., Ltd.
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
from webtest import app as webtest_app

from mistral import coordination
from mistral.tests.unit.api import base


class TestServicesController(base.FunctionalTest):
    def test_get_all(self):
        cfg.CONF.set_default('backend_url', 'zake://', 'coordination')

        coordination.cleanup_service_coordinator()
        service_coordinator = coordination.get_service_coordinator(
            my_id='service1'
        )
        service_coordinator.join_group('api_group')

        resp = self.app.get('/v2/services')

        self.assertEqual(resp.status_int, 200)

        self.assertEqual(len(resp.json['services']), 1)

        srv_ret = [{"name": "service1", "type": "api_group"}]
        self.assertItemsEqual(srv_ret, resp.json['services'])

    def test_get_all_raise(self):
        cfg.CONF.set_default('backend_url', None, 'coordination')

        coordination.cleanup_service_coordinator()
        coordination.get_service_coordinator()

        context = self.assertRaises(
            webtest_app.AppError,
            self.app.get,
            '/v2/services',
        )

        self.assertIn('Service API is not supported', context.message)
