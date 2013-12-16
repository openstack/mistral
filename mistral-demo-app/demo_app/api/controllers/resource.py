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

import logging
from wsme import types as wtypes


LOG = logging.getLogger(__name__)

API_STATUS = wtypes.Enum(str, 'SUPPORTED', 'CURRENT', 'DEPRECATED')


class Resource(wtypes.Base):
    """REST API Resource."""

    @classmethod
    def from_dict(cls, d):
        # TODO: take care of nested resources
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
