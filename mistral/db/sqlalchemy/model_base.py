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

from oslo_db.sqlalchemy import models as oslo_models
import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext import declarative
from sqlalchemy.orm import attributes

from mistral.services import security
from mistral import utils


def id_column():
    return sa.Column(
        sa.String(36),
        primary_key=True,
        default=utils.generate_unicode_uuid
    )


class _MistralModelBase(oslo_models.ModelBase, oslo_models.TimestampMixin):
    """Base class for all Mistral SQLAlchemy DB Models."""

    created_at = sa.Column(sa.DateTime, default=lambda: utils.utc_now_sec())
    updated_at = sa.Column(sa.DateTime, onupdate=lambda: utils.utc_now_sec())

    __table__ = None

    __hash__ = object.__hash__

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __eq__(self, other):
        if type(self) is not type(other):
            return False

        for col in self.__table__.columns:
            # In case of single table inheritance a class attribute
            # corresponding to a table column may not exist so we need
            # to skip these attributes.
            if (hasattr(self, col.name)
                and hasattr(other, col.name)
                    and getattr(self, col.name) != getattr(other, col.name)):
                return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_dict(self):
        """sqlalchemy based automatic to_dict method."""

        d = {col_name: col_val for col_name, col_val in self.iter_columns()}

        utils.datetime_to_str_in_dict(d, 'created_at')
        utils.datetime_to_str_in_dict(d, 'updated_at')

        return d

    def iter_column_names(self):
        """Returns an iterator for loaded column names.

        :return: A generator function for column names.
        """

        # If a column is unloaded at this point, it is
        # probably deferred. We do not want to access it
        # here and thereby cause it to load.
        unloaded = attributes.instance_state(self).unloaded

        for col in self.__table__.columns:
            if col.name not in unloaded and hasattr(self, col.name):
                yield col.name

    def iter_columns(self):
        """Returns an iterator for loaded columns.

        :return: A generator function that generates
            tuples (column name, column value).
        """

        for col_name in self.iter_column_names():
            yield col_name, getattr(self, col_name)

    def get_clone(self):
        """Clones current object, loads all fields and returns the result."""
        m = self.__class__()

        for col in self.__table__.columns:
            if hasattr(self, col.name):
                setattr(m, col.name, getattr(self, col.name))

        setattr(
            m,
            'created_at',
            utils.datetime_to_str(getattr(self, 'created_at'))
        )

        updated_at = getattr(self, 'updated_at')

        # NOTE(nmakhotkin): 'updated_at' field is empty for just created
        # object since it has not updated yet.
        if updated_at:
            setattr(m, 'updated_at', utils.datetime_to_str(updated_at))

        return m

    def __repr__(self):
        return '%s %s' % (type(self).__name__, self.to_dict().__repr__())


MistralModelBase = declarative.declarative_base(cls=_MistralModelBase)


# Secure model related stuff.


class MistralSecureModelBase(MistralModelBase):
    """Base class for all secure models."""

    __abstract__ = True

    scope = sa.Column(sa.String(80), default='private')
    project_id = sa.Column(sa.String(80), default=security.get_project_id)


def _set_project_id(target, value, oldvalue, initiator):
    return security.get_project_id()


def register_secure_model_hooks():
    # Make sure 'project_id' is always properly set.
    for sec_model_class in utils.iter_subclasses(MistralSecureModelBase):
        if '__abstract__' not in sec_model_class.__dict__:
            event.listen(
                sec_model_class.project_id,
                'set',
                _set_project_id,
                retval=True
            )
