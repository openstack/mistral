# Copyright 2018 - Nokia, Inc.
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


from mistral.tests.unit import base
from mistral.utils import filter_utils


class FilterUtilsTest(base.BaseTest):
    def test_create_filters_with_nones(self):
        expected_filters = {
            'key2': {'eq': 'value2'},
            'key1': {'eq': None}
        }

        filters = filter_utils.create_filters_from_request_params(
            none_values=['key1'],
            key1=None,
            key2='value2',
            key3=None,
        )

        self.assertEqual(expected_filters, filters)

        del expected_filters['key1']

        filters = filter_utils.create_filters_from_request_params(
            none_values=[],
            key1=None,
            key2='value2',
            key3=None,
        )

        self.assertEqual(expected_filters, filters)
