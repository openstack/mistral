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

import json
import logging

LOG = logging.getLogger(__name__)


class Resource(object):
    resource_name = 'Something'
    defaults = {}

    def __init__(self, manager, data):
        self.manager = manager
        self._data = data
        self._set_defaults()
        self._set_attributes()

    def _set_defaults(self):
        for k, v in self.defaults.iteritems():
            if k not in self._data:
                self._data[k] = v

    def _set_attributes(self):
        for k, v in self._data.iteritems():
            try:
                setattr(self, k, v)
            except AttributeError:
                # In this case we already defined the attribute on the class
                pass

    def __str__(self):
        vals = ", ".join(["%s='%s'" % (n, v)
                          for n, v in self._data.iteritems()])
        return "%s [%s]" % (self.resource_name, vals)


def _check_items(obj, searches):
    try:
        return all(getattr(obj, attr) == value for (attr, value) in searches)
    except AttributeError:
        return False


def extract_json(response, response_key):
    if response_key is not None:
        return get_json(response)[response_key]
    else:
        return get_json(response)


class ResourceManager(object):
    resource_class = None

    def __init__(self, client):
        self.client = client

    def find(self, **kwargs):
        return [i for i in self.list() if _check_items(i, kwargs.items())]

    def _ensure_not_empty(self, **kwargs):
        for name, value in kwargs.iteritems():
            if value is None or (isinstance(value, str) and len(value) == 0):
                raise APIException('%s is missing field "%s"' %
                                   (self.resource_class.__name__, name))

    def _copy_if_defined(self, data, **kwargs):
        for name, value in kwargs.iteritems():
            if value is not None:
                data[name] = value

    def _create(self, url, data, response_key=None, dump_json=True):
        if dump_json:
            data = json.dumps(data)

        resp = self.client.http_client.post(url, data)

        if resp.status_code != 201:
            self._raise_api_exception(resp)

        return self.resource_class(self, extract_json(resp, response_key))

    def _update(self, url, data, response_key=None, dump_json=True):
        if dump_json:
            data = json.dumps(data)

        resp = self.client.http_client.put(url, data)

        if resp.status_code != 200:
            self._raise_api_exception(resp)

        return self.resource_class(self, extract_json(resp, response_key))

    def _list(self, url, response_key=None):
        resp = self.client.http_client.get(url)

        if resp.status_code == 200:
            return [self.resource_class(self, resource_data)
                    for resource_data in extract_json(resp, response_key)]
        else:
            self._raise_api_exception(resp)

    def _get(self, url, response_key=None):
        resp = self.client.http_client.get(url)

        if resp.status_code == 200:
            return self.resource_class(self, extract_json(resp, response_key))
        else:
            self._raise_api_exception(resp)

    def _delete(self, url):
        resp = self.client.http_client.delete(url)

        if resp.status_code != 204:
            self._raise_api_exception(resp)

    def _plurify_resource_name(self):
        return self.resource_class.resource_name + 's'

    def _raise_api_exception(self, resp):
        error_data = get_json(resp)
        raise APIException(error_data["faultstring"])


def get_json(response):
    """This method provided backward compatibility with old versions
    of requests library

    """
    json_field_or_function = getattr(response, 'json', None)

    if callable(json_field_or_function):
        return response.json()
    else:
        return json.loads(response.content)


class APIException(Exception):
    pass
