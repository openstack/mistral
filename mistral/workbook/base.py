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

from mistral import exceptions


class BaseSpec(object):
    _required_keys = []

    def __init__(self, data):
        self._data = data

    def validate(self):
        if not all(k in self._data for k in self._required_keys):
            message = ("Wrong model definition for: %s. It should contain"
                       " required keys: %s" % (self.__class__.__name__,
                                               self._required_keys))
            raise exceptions.InvalidModelException(message)
        return True

    def to_dict(self):
        return self._data


class BaseSpecList(object):
    item_class = None

    def __init__(self, data):
        self.items = {}

        for k, v in data.items():
            v['name'] = k
            self.items[k] = self.item_class(v)

        for name in self:
            self.get(name).validate()

    def __iter__(self):
        return iter(self.items)

    def __getitem__(self, name):
        return self.items.get(name)

    def __len__(self):
        return len(self.items)

    def get(self, name):
        return self.__getitem__(name)
