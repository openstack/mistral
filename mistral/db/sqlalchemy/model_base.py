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

from sqlalchemy.ext import declarative
from sqlalchemy.orm import attributes

from mistral.openstack.common.db.sqlalchemy import models as oslo_models


class _MistralBase(oslo_models.ModelBase, oslo_models.TimestampMixin):
    """Base class for all Mistral SQLAlchemy DB Models."""

    __table__ = None

    def to_dict(self):
        """sqlalchemy based automatic to_dict method."""
        d = {}

        # if a column is unloaded at this point, it is
        # probably deferred. We do not want to access it
        # here and thereby cause it to load...
        unloaded = attributes.instance_state(self).unloaded

        for col in self.__table__.columns:
            if col.name not in unloaded:
                d[col.name] = getattr(self, col.name)

        datetime_to_str(d, 'created_at')
        datetime_to_str(d, 'updated_at')

        return d


def datetime_to_str(dct, attr_name):
    if dct.get(attr_name) is not None:
        dct[attr_name] = dct[attr_name].isoformat(' ')


MistralBase = declarative.declarative_base(cls=_MistralBase)
