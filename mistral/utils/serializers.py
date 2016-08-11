# Copyright 2014 - Mirantis, Inc.
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

import abc

from oslo_serialization import jsonutils


class Serializer(object):
    @staticmethod
    @abc.abstractmethod
    def serialize(entity):
        pass

    @staticmethod
    @abc.abstractmethod
    def deserialize(entity):
        pass


class KombuSerializer(Serializer):
    @staticmethod
    def deserialize(entity):
        return jsonutils.loads(entity)

    @staticmethod
    def serialize(entity):
        return jsonutils.dumps(
            jsonutils.to_primitive(entity, convert_instances=True)
        )
