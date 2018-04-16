#    Copyright 2018 Nokia Networks.
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

import mock

from mistral.actions import std_actions as std
from mistral.tests.unit import base


class TestDictActionTest(base.BaseTest):
    def test_default_inputs(self):
        dict_size = 99

        action = std.TestDictAction(dict_size, key_prefix='key', val='val')

        d = action.run(mock.Mock())

        self.assertIsNotNone(d)
        self.assertEqual(dict_size, len(d))
        self.assertIn('key0', d)
        self.assertIn('key{}'.format(dict_size - 1), d)
