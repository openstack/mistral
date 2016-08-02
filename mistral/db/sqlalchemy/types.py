# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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
#
#   This module implements SQLAlchemy-based types for dict and list
#   expressed by json-strings
#

from oslo_serialization import jsonutils
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.ext import mutable


class JsonEncoded(sa.TypeDecorator):
    """Represents an immutable structure as a json-encoded string."""

    impl = sa.Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = jsonutils.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = jsonutils.loads(value)
        return value


class MutableList(mutable.Mutable, list):
    @classmethod
    def coerce(cls, key, value):
        """Convert plain lists to MutableList."""
        if not isinstance(value, MutableList):
            if isinstance(value, list):
                return MutableList(value)

            # this call will raise ValueError
            return mutable.Mutable.coerce(key, value)
        return value

    def __add__(self, value):
        """Detect list add events and emit change events."""
        list.__add__(self, value)
        self.changed()

    def append(self, value):
        """Detect list add events and emit change events."""
        list.append(self, value)
        self.changed()

    def __setitem__(self, key, value):
        """Detect list set events and emit change events."""
        list.__setitem__(self, key, value)
        self.changed()

    def __delitem__(self, i):
        """Detect list del events and emit change events."""
        list.__delitem__(self, i)
        self.changed()


def JsonDictType():
    """Returns an SQLAlchemy Column Type suitable to store a Json dict."""
    return mutable.MutableDict.as_mutable(JsonEncoded)


def JsonListType():
    """Returns an SQLAlchemy Column Type suitable to store a Json array."""
    return MutableList.as_mutable(JsonEncoded)


def MediumText():
    # TODO(rakhmerov): Need to do for postgres.
    return sa.Text().with_variant(mysql.MEDIUMTEXT(), 'mysql')


class JsonEncodedMediumText(JsonEncoded):
    impl = MediumText()


def JsonMediumDictType():
    return mutable.MutableDict.as_mutable(JsonEncodedMediumText)


def LongText():
    # TODO(rakhmerov): Need to do for postgres.
    return sa.Text().with_variant(mysql.LONGTEXT(), 'mysql')


class JsonEncodedLongText(JsonEncoded):
    impl = LongText()


def JsonLongDictType():
    return mutable.MutableDict.as_mutable(JsonEncodedLongText)
