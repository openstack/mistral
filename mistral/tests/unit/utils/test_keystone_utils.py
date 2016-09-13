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

from mistral import config
from mistral.tests.unit import base
from mistral.utils.openstack import keystone

SERVICES_CATALOG = [
    {
        "type": "compute",
        "name": "nova",
        "endpoints": [
            {
                "interface": "private",
                "url": "https://example.com/nova/private",
                "region": "RegionOne"
            },
            {
                "interface": "public",
                "url": "https://example.com/nova/public",
                "region": "RegionOne"
            },
            {
                "interface": "internal",
                "url": "https://example.com/nova/internal",
                "region": "RegionOne"
            }
        ]
    },
    {
        "type": "compute",
        "name": "nova2",
        "endpoints": [
            {
                "interface": "public",
                "url": "https://example.com/nova2/public/r1",
                "region": "RegionOne"
            },
            {
                "interface": "public",
                "url": "https://example.com/nova2/public/r2",
                "region": "RegionTwo"
            },
            {
                "interface": "internal",
                "url": "https://example.com/nova2/internal",
                "region": "RegionTwo"
            }
        ]
    },
    {
        "type": "orchestration",
        "name": "heat",
        "endpoints": [
            {
                "interface": "private",
                "url": "https://example.com/heat/private",
                "region": "RegionOne"
            },
            {
                "interface": "public",
                "url": "https://example.com/heat/public",
                "region": "RegionOne"
            },
            {
                "interface": "internal",
                "url": "https://example.com/heat/internal",
                "region": "RegionTwo"
            }
        ]
    }
]


class KeystoneUtilsTest(base.BaseTest):
    def setUp(self):
        super(KeystoneUtilsTest, self).setUp()

        self.values = {'id': 'my_id'}

    def override_config(self, name, override, group=None):
        config.CONF.set_override(name, override, group)
        self.addCleanup(config.CONF.clear_override, name, group)

    def test_format_url_dollar_sign(self):
        url_template = "http://host:port/v1/$(id)s"

        expected = "http://host:port/v1/my_id"

        self.assertEqual(
            expected,
            keystone.format_url(url_template, self.values)
        )

    def test_format_url_percent_sign(self):
        url_template = "http://host:port/v1/%(id)s"

        expected = "http://host:port/v1/my_id"

        self.assertEqual(
            expected,
            keystone.format_url(url_template, self.values)
        )

    def test_service_endpoints_select_default(self):
        def find(name, typ=None, catalog=SERVICES_CATALOG):
            return keystone.select_service_endpoints(name, typ, catalog)

        endpoints = find('nova', 'compute')
        self.assertEqual('https://example.com/nova/public', endpoints[0].url,
                         message='public interface must be selected')

        endpoints = find('nova2')
        self.assertEqual(2, len(endpoints),
                         message='public endpoints must be selected '
                                 'in each region')

        endpoints = find('heat')
        self.assertEqual('https://example.com/heat/public', endpoints[0].url,
                         message='selection should work without type set')

        endpoints = find('nova', None, [])
        self.assertEqual([], endpoints,
                         message='empty catalog should be accepted')

    def test_service_endpoints_select_internal(self):
        def find(name, typ=None, catalog=SERVICES_CATALOG):
            return keystone.select_service_endpoints(name, typ, catalog)

        self.override_config('os_actions_endpoint_type', 'internal')
        endpoints = find('nova', 'compute')
        self.assertEqual('https://example.com/nova/internal', endpoints[0].url,
                         message='internal interface must be selected')

        endpoints = find('nova2')
        self.assertEqual("https://example.com/nova2/internal",
                         endpoints[0].url,
                         message='internal endpoints must be selected '
                                 'in each region')

        endpoints = find('heat')
        self.assertEqual('https://example.com/heat/internal', endpoints[0].url,
                         message='selection should work without type set')
