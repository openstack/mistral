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
    def from_dict(cls, d):
        obj = cls()

        for key, val in d.items():
            if hasattr(obj, key):
                setattr(obj, key, val)

        return obj

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
        resource_collection = cls()

        setattr(resource_collection, resource_collection._type, resources)

        resource_collection.next = resource_collection.get_next(
            limit,
            url=url,
            fields=fields,
            **kwargs
        )

        return resource_collection

    def has_next(self, limit):
        """Return whether resources has more items."""
        return len(self.collection) and len(self.collection) == limit

    def get_next(self, limit, url=None, fields=None, **kwargs):
        """Return a link to the next subset of the resources."""
        if not self.has_next(limit):
            return wtypes.Unset

        q_args = ''.join(
            ['%s=%s&' % (key, value) for key, value in kwargs.items()]
        )

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

    @classmethod
    def sample(cls):
        return cls(href='http://example.com/here',
                   target='here')
