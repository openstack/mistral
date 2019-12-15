# Copyright 2017 - Nokia Networks
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

from mistral.api.controllers.v2 import types
from mistral import exceptions as exc
from mistral.tests.unit import base
from mistral.utils import filter_utils


class TestTypesController(base.BaseTest):

    base_id = '88888888-4444-4444-4444-777777755555'
    uuid_type = types.uuid

    def test_uuid_type(self):
        self.uuid_type.validate(self.base_id)

    def test_uuid_type_wit_invalid_format(self):
        self.assertRaises(exc.InputException,
                          self.uuid_type.validate, 'invalid_format')
        self.assertRaises(exc.InputException,
                          self.uuid_type.validate, '44-231-454-542123')

    def test_uuid_with_filters(self):
        for filter_type in filter_utils.ALL:
            value = '{}{}'.format(filter_type + ':', self.base_id)
            if filter_type.startswith((filter_utils.IN, filter_utils.NOT_IN)):
                self.assertRaises(exc.InputException,
                                  self.uuid_type.validate, value)
            else:
                self.uuid_type.validate(value)

    def test_uuid_type_with_invalid_prefix(self):
        value = 'invalid:{}'.format(self.base_id)
        self.assertRaises(exc.InputException, self.uuid_type.validate, value)
