# Copyright 2017 - Nokia Networks.
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

from mistral import serialization
from mistral.tests.unit import base


class MyClass(serialization.MistralSerializable):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __eq__(self, other):
        if not isinstance(other, MyClass):
            return False

        return other.a == self.a and other.b == self.b


class MyClassSerializer(serialization.DictBasedSerializer):
    def serialize_to_dict(self, entity):
        return {'a': entity.a, 'b': entity.b}

    def deserialize_from_dict(self, entity_dict):
        return MyClass(entity_dict['a'], entity_dict['b'])


class SerializationTest(base.BaseTest):
    def setUp(self):
        super(SerializationTest, self).setUp()

        serialization.register_serializer(MyClass, MyClassSerializer())

        self.addCleanup(serialization.unregister_serializer, MyClass)

    def test_dict_based_serializer(self):
        obj = MyClass('a', 'b')

        serializer = MyClassSerializer()

        s = serializer.serialize(obj)

        self.assertEqual(obj, serializer.deserialize(s))

        self.assertIsNone(serializer.serialize(None))
        self.assertIsNone(serializer.deserialize(None))

    def test_polymorphic_serializer_primitive_types(self):
        serializer = serialization.get_polymorphic_serializer()

        self.assertEqual(17, serializer.deserialize(serializer.serialize(17)))
        self.assertEqual(
            0.34,
            serializer.deserialize(serializer.serialize(0.34))
        )
        self.assertEqual(-5, serializer.deserialize(serializer.serialize(-5)))
        self.assertEqual(
            -6.3,
            serializer.deserialize(serializer.serialize(-6.3))
        )
        self.assertFalse(serializer.deserialize(serializer.serialize(False)))
        self.assertTrue(serializer.deserialize(serializer.serialize(True)))
        self.assertEqual(
            'abc',
            serializer.deserialize(serializer.serialize('abc'))
        )
        self.assertEqual(
            {'a': 'b', 'c': 'd'},
            serializer.deserialize(serializer.serialize({'a': 'b', 'c': 'd'}))
        )
        self.assertEqual(
            ['a', 'b', 'c'],
            serializer.deserialize(serializer.serialize(['a', 'b', 'c']))
        )

    def test_polymorphic_serializer_custom_object(self):
        serializer = serialization.get_polymorphic_serializer()

        obj = MyClass('a', 'b')

        s = serializer.serialize(obj)

        self.assertIn('__serial_key', s)
        self.assertIn('__serial_data', s)

        self.assertEqual(obj, serializer.deserialize(s))

        self.assertIsNone(serializer.serialize(None))
        self.assertIsNone(serializer.deserialize(None))

    def test_register_twice(self):
        self.assertRaises(
            RuntimeError,
            serialization.register_serializer,
            MyClass,
            MyClassSerializer()
        )
