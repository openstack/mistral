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
import jsonschema
import re
import six

from mistral import exceptions as exc


CMD_PTRN = re.compile("^[\w\.]+[^=\s\"]*")
PARAMS_PTRN = re.compile("([\w]+)=(\"[^=]*\"|\'[^=]*'|"
                         "\{[^=]*\}|\[[^=]*\]|[\.,:\w\d\.]*)")


class BaseSpec(object):
    # See http://json-schema.org
    _schema = {
        "type": "object",
    }

    _version = "1.0"

    def __init__(self, data):
        self._data = data

        self.validate()

    def validate(self):
        try:
            jsonschema.validate(self._data, self._schema)
        except jsonschema.ValidationError as e:
            raise exc.InvalidModelException("Invalid DSL: %s" % e)

    def _spec_property(self, prop_name, spec_cls):
        prop_val = self._data.get(prop_name)

        return spec_cls(prop_val) if prop_val else None

    def _inject_version(self, prop_names):
        for prop_name in prop_names:
            prop_data = self._data.get(prop_name)

            if isinstance(prop_data, dict):
                prop_data['version'] = self._version

    def _as_dict(self, prop_name):
        prop_val = self._data.get(prop_name)

        if not prop_val:
            return {}

        if isinstance(prop_val, dict):
            return prop_val
        elif isinstance(prop_val, list):
            result = {}
            for t in prop_val:
                result.update(t if isinstance(t, dict) else {t: ''})
            return result
        elif isinstance(prop_val, six.string_types):
            return {prop_val: ''}

    def _as_list_of_tuples(self, prop_name):
        prop_val = self._data.get(prop_name)

        if not prop_val:
            return []

        return [self._as_tuple(item) for item in prop_val]

    @staticmethod
    def _as_tuple(val):
        return val.items()[0] if isinstance(val, dict) else (val, '')

    @staticmethod
    def _parse_cmd_and_input(cmd_str):
        # TODO(rakhmerov): Try to find a way with one expression.
        cmd_matcher = CMD_PTRN.search(cmd_str)

        if not cmd_matcher:
            msg = "Invalid action/workflow task property: %s" % cmd_str
            raise exc.InvalidModelException(msg)

        cmd = cmd_matcher.group()

        params = {}
        for k, v in re.findall(PARAMS_PTRN, cmd_str):
            # Remove embracing quotes.
            if v[0] == '"' or v[0] == "'":
                v = v[1:-1]
            else:
                try:
                    v = json.loads(v)
                except Exception:
                    pass

            params[k] = v

        return cmd, params

    def to_dict(self):
        return self._data

    def get_version(self):
        return self._version


class BaseSpecList(object):
    item_class = None

    _version = '1.0'

    def __init__(self, data):
        self.items = {}

        for k, v in data.iteritems():
            if k != 'version':
                v['name'] = k
                v['version'] = self._version
                self.items[k] = self.item_class(v)

    def item_keys(self):
        return self.items.keys()

    def __iter__(self):
        return self.items.itervalues()

    def __getitem__(self, name):
        return self.items.get(name)

    def __len__(self):
        return len(self.items)

    def get(self, name):
        return self.__getitem__(name)
