# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from yaql.language import utils as yaql_utils

from mistral.tests.unit import base
from mistral import utils


class YaqlJsonSerializationTest(base.BaseTest):
    def test_serialize_frozen_dict(self):
        data = yaql_utils.FrozenDict(a=1, b=2, c=iter([1, 2, 3]))

        json_str = utils.to_json_str(data)

        self.assertIsNotNone(json_str)

        self.assertIn('"a": 1', json_str)
        self.assertIn('"b": 2', json_str)
        self.assertIn('"c": [1, 2, 3]', json_str)

    def test_serialize_generator(self):
        def _list_stream(_list):
            for i in _list:
                yield i

        gen = _list_stream(
            [1, yaql_utils.FrozenDict(a=1), _list_stream([12, 15])]
        )

        self.assertEqual('[1, {"a": 1}, [12, 15]]', utils.to_json_str(gen))

    def test_serialize_dict_of_generators(self):
        def _f(cnt):
            for i in range(1, cnt + 1):
                yield i

        data = {'numbers': _f(3)}

        self.assertEqual('{"numbers": [1, 2, 3]}', utils.to_json_str(data))

    def test_serialize_range(self):
        self.assertEqual("[1, 2, 3, 4]", utils.to_json_str(range(1, 5)))

    def test_serialize_iterator_of_frozen_dicts(self):
        data = iter(
            [
                yaql_utils.FrozenDict(a=1, b=2, c=iter([1, 2, 3])),
                yaql_utils.FrozenDict(
                    a=11,
                    b=yaql_utils.FrozenDict(b='222'),
                    c=iter(
                        [
                            1,
                            yaql_utils.FrozenDict(
                                a=iter([4, yaql_utils.FrozenDict(a=99)])
                            )
                        ]
                    )
                )
            ]
        )

        json_str = utils.to_json_str(data)

        self.assertIsNotNone(json_str)

        # Checking the first item.
        self.assertIn('"a": 1', json_str)
        self.assertIn('"b": 2', json_str)
        self.assertIn('"c": [1, 2, 3]', json_str)

        # Checking the first item.
        self.assertIn('"a": 11', json_str)
        self.assertIn('"b": {"b": "222"}', json_str)
        self.assertIn('"c": [1, {"a": [4, {"a": 99}]}]', json_str)
