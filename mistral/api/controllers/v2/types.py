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
import json

from oslo_utils import uuidutils
import six
from wsme import types as wtypes

from mistral import exceptions as exc


class ListType(wtypes.UserType):
    """A simple list type."""

    basetype = wtypes.text
    name = 'list'

    @staticmethod
    def validate(value):
        """Validate and convert the input to a ListType.

        :param value: A comma separated string of values
        :returns: A list of values.
        """
        items = [v.strip().lower() for v in six.text_type(value).split(',')]

        # remove empty items.
        return [x for x in items if x]

    @staticmethod
    def frombasetype(value):
        return ListType.validate(value) if value is not None else None


class UniqueListType(ListType):
    """A simple list type with no duplicate items."""

    name = 'uniquelist'

    @staticmethod
    def validate(value):
        """Validate and convert the input to a UniqueListType.

        :param value: A comma separated string of values.
        :returns: A list with no duplicate items.
        """
        items = ListType.validate(value)

        seen = set()

        return [x for x in items if not (x in seen or seen.add(x))]

    @staticmethod
    def frombasetype(value):
        return UniqueListType.validate(value) if value is not None else None


class UuidType(wtypes.UserType):
    """A simple UUID type.

    The builtin UuidType class in wsme.types doesn't work properly with pecan.
    """

    basetype = wtypes.text
    name = 'uuid'

    @staticmethod
    def validate(value):
        if not uuidutils.is_uuid_like(value):
            raise exc.InputException(
                "Expected a uuid but received %s." % value
            )

        return value

    @staticmethod
    def frombasetype(value):
        return UuidType.validate(value) if value is not None else None


class JsonType(wtypes.UserType):
    """A simple JSON type."""

    basetype = wtypes.text
    name = 'json'

    def validate(self, value):
        if not value:
            return {}

        if not isinstance(value, dict):
            raise exc.InputException(
                'JsonType field value must be a dictionary [actual=%s]' % value
            )

        return value

    def frombasetype(self, value):
        if isinstance(value, dict):
            return value
        try:
            return json.loads(value) if value is not None else None
        except TypeError as e:
            raise ValueError(e)

    def tobasetype(self, value):
        # Value must be a dict.
        return json.dumps(value) if value is not None else None


uuid = UuidType()
list = ListType()
uniquelist = UniqueListType()
jsontype = JsonType()
