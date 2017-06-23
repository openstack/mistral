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

from mistral_lib import serialization as ml_serialization
from oslo_serialization import jsonutils

_SERIALIZER = None

# Backwards compatibility
Serializer = ml_serialization.Serializer
DictBasedSerializer = ml_serialization.DictBasedSerializer
MistralSerializable = ml_serialization.MistralSerializable


# PolymorphicSerializer cannot be used from mistral-lib yet
# as mistral-lib does not have the unregister method.
# Once it does this will be removed also in favor of mistral-lib


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

    def unregister(self, entity_cls):
        key = self._get_serialization_key(entity_cls)

        if not key:
            return

        if key in self.serializers:
            del self.serializers[key]

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

        if not serializer:
            raise RuntimeError(
                "Failed to find a serializer for the key: %s" % key
            )

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


def unregister_serializer(entity_cls):
    get_polymorphic_serializer().unregister(entity_cls)


def cleanup():
    get_polymorphic_serializer().cleanup()
