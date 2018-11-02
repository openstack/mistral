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

import json

from wsme import types as wtypes

from mistral import utils


class Resource(wtypes.Base):
    """REST API Resource."""

    _wsme_attributes = []

    def to_dict(self):
        d = {}

        for attr in self._wsme_attributes:
            attr_val = getattr(self, attr.name)

            if not isinstance(attr_val, wtypes.UnsetType):
                d[attr.name] = attr_val

        return d

    @classmethod
    def from_tuples(cls, tuple_iterator):
        obj = cls()

        for col_name, col_val in tuple_iterator:
            if hasattr(obj, col_name):
                # Convert all datetime values to strings.
                setattr(obj, col_name, utils.datetime_to_str(col_val))

        return obj

    @classmethod
    def from_dict(cls, d):
        return cls.from_tuples(d.items())

    @classmethod
    def from_db_model(cls, db_model):
        return cls.from_tuples(db_model.iter_columns())

    def __str__(self):
        """WSME based implementation of __str__."""

        res = "%s [" % type(self).__name__

        first = True
        for attr in self._wsme_attributes:
            if not first:
                res += ', '
            else:
                first = False

            res += "%s='%s'" % (attr.name, getattr(self, attr.name))

        return res + "]"

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def get_fields(cls):
        obj = cls()

        return [attr.name for attr in obj._wsme_attributes]


class ResourceList(Resource):
    """Resource containing the list of other resources."""

    next = wtypes.text
    """A link to retrieve the next subset of the resource list"""

    @property
    def collection(self):
        return getattr(self, self._type)

    @classmethod
    def convert_with_links(cls, resources, limit, url=None, fields=None,
                           **kwargs):
        resource_list = cls()

        setattr(resource_list, resource_list._type, resources)

        resource_list.next = resource_list.get_next(
            limit,
            url=url,
            fields=fields,
            **kwargs
        )

        return resource_list

    def has_next(self, limit):
        """Return whether resources has more items."""
        return len(self.collection) and len(self.collection) == limit

    def get_next(self, limit, url=None, fields=None, **kwargs):
        """Return a link to the next subset of the resources."""
        if not self.has_next(limit):
            return wtypes.Unset

        q_args = ''

        for key, value in kwargs.items():
            if isinstance(value, dict):
                q_args += '%s=%s:%s&' % \
                          (key, list(value.keys())[0], list(value.values())[0])
            else:
                q_args += '%s=%s&' % (key, value)

        resource_args = (
            '?%(args)slimit=%(limit)d&marker=%(marker)s' %
            {
                'args': q_args,
                'limit': limit,
                'marker': self.collection[-1].id
            }
        )

        # Fields is handled specially here, we can move it above when it's
        # supported by all resources query.
        if fields:
            resource_args += '&fields=%s' % fields

        next_link = "%(host_url)s/v2/%(resource)s%(args)s" % {
            'host_url': url,
            'resource': self._type,
            'args': resource_args
        }

        return next_link

    def to_dict(self):
        d = {}

        for attr in self._wsme_attributes:
            attr_val = getattr(self, attr.name)

            if isinstance(attr_val, list):
                if isinstance(attr_val[0], Resource):
                    d[attr.name] = [v.to_dict() for v in attr_val]
            elif not isinstance(attr_val, wtypes.UnsetType):
                d[attr.name] = attr_val

        return d


class Link(Resource):
    """Web link."""

    href = wtypes.text
    target = wtypes.text
    rel = wtypes.text

    @classmethod
    def sample(cls):
        return cls(href='http://example.com/here',
                   target='here', rel='self')
