#    Copyright 2017 Nokia Networks.
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

import abc

from oslo_serialization import jsonutils


_SERIALIZER = None


class Serializer(object):
    """Base interface for entity serializers.

    A particular serializer knows how to convert a certain object
    into a string and back from that string into an object whose
    state is equivalent to the initial object.
    """

    @abc.abstractmethod
    def serialize(self, entity):
        """Converts the given object into a string.

        :param entity: A object to be serialized.
        :return String containing the state of the object in serialized form.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def deserialize(self, data_str):
        """Converts the given string into an object.

        :param data_str: String containing the state of the object in
            serialized form.
        :return: An object.
        """
        raise NotImplementedError


class DictBasedSerializer(Serializer):
    """Dictionary-based serializer.

    It slightly simplifies implementing custom serializers by introducing
    a contract based on dictionary. A serializer class extending this class
    just needs to implement conversion from object into dict and from dict
    to object. It doesn't need to convert into string and back as required
    bye the base serializer contract. Conversion into string is implemented
    once with regard to possible problems that may occur for collection and
    primitive types as circular dependencies, correct date format etc.
    """

    def serialize(self, entity):
        if entity is None:
            return None

        entity_dict = self.serialize_to_dict(entity)

        return jsonutils.dumps(
            jsonutils.to_primitive(entity_dict, convert_instances=True)
        )

    def deserialize(self, data_str):
        if data_str is None:
            return None

        entity_dict = jsonutils.loads(data_str)

        return self.deserialize_from_dict(entity_dict)

    @abc.abstractmethod
    def serialize_to_dict(self, entity):
        raise NotImplementedError

    @abc.abstractmethod
    def deserialize_from_dict(self, entity_dict):
        raise NotImplementedError


class MistralSerializable(object):
    """A mixin to generate a serialization key for a custom object."""

    @classmethod
    def get_serialization_key(cls):
        return "%s.%s" % (cls.__module__, cls.__name__)


class PolymorphicSerializer(Serializer):
    """Polymorphic serializer.

    The purpose of this class is to server as a serialization router
    between serializers that can work with entities of particular type.
    All concrete serializers associated with concrete entity classes
    should be registered via method 'register', after that an instance
    of polymorphic serializer can be used as a universal serializer
    for an RPC system or something else.
    When converting an object into a string this serializer also writes
    a special key into the result string sequence so that it's possible
    to find a proper serializer when deserializing this object.
    If a primitive value is given as an entity this serializer doesn't
    do anything special and simply converts a value into a string using
    jsonutils. Similar when it converts a string into a primitive value.
    """

    def __init__(self):
        # {serialization key: serializer}
        self.serializers = {}

    @staticmethod
    def _get_serialization_key(entity_cls):
        if issubclass(entity_cls, MistralSerializable):
            return entity_cls.get_serialization_key()

        return None

    def register(self, entity_cls, serializer):
        key = self._get_serialization_key(entity_cls)

        if not key:
            return

        if key in self.serializers:
            raise RuntimeError(
                "A serializer for the entity class has already been"
                " registered: %s" % entity_cls
            )

        self.serializers[key] = serializer

    def cleanup(self):
        self.serializers.clear()

    def serialize(self, entity):
        if entity is None:
            return None

        key = self._get_serialization_key(type(entity))

        # Primitive or not registered type.
        if not key:
            return jsonutils.dumps(
                jsonutils.to_primitive(entity, convert_instances=True)
            )

        serializer = self.serializers.get(key)

        result = {
            '__serial_key': key,
            '__serial_data': serializer.serialize(entity)
        }

        return jsonutils.dumps(result)

    def deserialize(self, data_str):
        if data_str is None:
            return None

        data = jsonutils.loads(data_str)

        if isinstance(data, dict) and '__serial_key' in data:
            serializer = self.serializers.get(data['__serial_key'])

            return serializer.deserialize(data['__serial_data'])

        return data


def get_polymorphic_serializer():
    global _SERIALIZER

    if _SERIALIZER is None:
        _SERIALIZER = PolymorphicSerializer()

    return _SERIALIZER


def register_serializer(entity_cls, serializer):
    get_polymorphic_serializer().register(entity_cls, serializer)


def cleanup():
    get_polymorphic_serializer().cleanup()
