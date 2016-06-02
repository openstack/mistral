# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

import copy
import json
import jsonschema
import re
import six

from mistral import exceptions as exc
from mistral import expressions as expr
from mistral import utils
from mistral.workbook import types


CMD_PTRN = re.compile("^[\w\.]+[^=\(\s\"]*")

INLINE_YAQL = expr.INLINE_YAQL_REGEXP
_ALL_IN_BRACKETS = "\[.*\]\s*"
_ALL_IN_QUOTES = "\"[^\"]*\"\s*"
_ALL_IN_APOSTROPHES = "'[^']*'\s*"
_DIGITS = "\d+"
_TRUE = "true"
_FALSE = "false"
_NULL = "null"

ALL = (
    _ALL_IN_QUOTES, _ALL_IN_APOSTROPHES, INLINE_YAQL,
    _ALL_IN_BRACKETS, _TRUE, _FALSE, _NULL, _DIGITS
)

PARAMS_PTRN = re.compile("([-_\w]+)=(%s)" % "|".join(ALL))


def instantiate_spec(spec_cls, data):
    """Instantiates specification accounting for specification hierarchies.

    :param spec_cls: Specification concrete or base class. In case if base
        class or the hierarchy is provided this method relies on attributes
        _polymorphic_key and _polymorphic_value in order to find a concrete
        class that needs to be instantiated.
    :param data: Raw specification data as a dictionary.
    """

    if issubclass(spec_cls, BaseSpecList):
        # Ignore polymorphic search for specification lists because
        # it doesn't make sense for them.
        return spec_cls(data)

    if not hasattr(spec_cls, '_polymorphic_key'):
        spec = spec_cls(data)

        spec.validate_semantics()

        return spec

    key = spec_cls._polymorphic_key

    if not isinstance(key, tuple):
        key_name = key
        key_default = None
    else:
        key_name = key[0]
        key_default = key[1]

    for cls in utils.iter_subclasses(spec_cls):
        if not hasattr(cls, '_polymorphic_value'):
            raise exc.DSLParsingException(
                "Class '%s' is expected to have attribute '_polymorphic_value'"
                " because it's a part of specification hierarchy inherited "
                "from class '%s'." % (cls, spec_cls)
            )

        if cls._polymorphic_value == data.get(key_name, key_default):
            spec = cls(data)

            spec.validate_semantics()

            return spec

    raise exc.DSLParsingException(
        'Failed to find a specification class to instantiate '
        '[spec_cls=%s, data=%s]' % (spec_cls, data)
    )


class BaseSpec(object):
    """Base class for all DSL specifications.

    It represents a DSL entity such as workflow or task as a python object
    providing more convenient API to analyse DSL than just working with raw
    data in form of a dictionary. Specification classes also implement
    all required validation logic by overriding instance method 'validate()'.

    Note that the specification mechanism allows to have polymorphic entities
    in DSL. For example, if we find it more convenient to have separate
    specification classes for different types of workflow (i.e. 'direct' and
    'reverse') we can do so. In this case, in order to instantiate them
    correctly method 'instantiate_spec' must always be used where argument
    'spec_cls' must be a root class of the specification hierarchy containing
    class attribute '_polymorhpic_key' pointing to a key in raw data relying
    on which we can find a concrete class. Concrete classes then must all have
    attribute '_polymorhpic_value' corresponding to a value in a raw data.
    Attribute '_polymorhpic_key' can be either a string or a tuple of size two
    where the first value is a key name itself and the second value is a
    default polymorphic value that must be used if raw data doesn't contain
    a configured key at all. An example of this situation is when we don't
    specify a workflow type in DSL. In this case, we assume it's 'direct'.
    """

    # See http://json-schema.org
    _schema = {
        'type': 'object'
    }

    _meta_schema = {
        'type': 'object'
    }

    _definitions = {}

    _version = '1.0'

    @classmethod
    def get_schema(cls, includes=['meta', 'definitions']):
        schema = copy.deepcopy(cls._schema)

        schema['properties'] = utils.merge_dicts(
            schema.get('properties', {}),
            cls._meta_schema.get('properties', {}),
            overwrite=False
        )

        if includes and 'meta' in includes:
            schema['required'] = list(
                set(schema.get('required', []) +
                    cls._meta_schema.get('required', []))
            )

        if includes and 'definitions' in includes:
            schema['definitions'] = utils.merge_dicts(
                schema.get('definitions', {}),
                cls._definitions,
                overwrite=False
            )

        return schema

    def __init__(self, data):
        self._data = data

        self.validate_schema()

    def validate_schema(self):
        """Validates DSL entity schema that this specification represents.

        By default, this method just validate schema of DSL entity that this
        specification represents using "_schema" class attribute.
        Additionally, child classes may implement additional logic to validate
        more specific things like YAQL expressions in their fields.

        Note that this method is called before construction of specification
        fields and validation logic should only rely on raw data provided as
        a dictionary accessible through '_data' instance field.
        """

        try:
            jsonschema.validate(self._data, self.get_schema())
        except jsonschema.ValidationError as e:
            raise exc.InvalidModelException("Invalid DSL: %s" % e)

    def validate_semantics(self):
        """Validates semantics of specification object.

        Child classes may implement validation logic to check things like
        integrity of corresponding data structure (e.g. task graph) or
        other things that can't be expressed in JSON schema.

        This method is called after specification has been built (i.e.
        its initializer has finished it's work) so that validation logic
        can rely on initialized specification fields.
        """
        pass

    def validate_yaql_expr(self, dsl_part):
        if isinstance(dsl_part, six.string_types):
            expr.validate(dsl_part)
        elif isinstance(dsl_part, list):
            for expression in dsl_part:
                if isinstance(expression, six.string_types):
                    expr.validate(expression)
        elif isinstance(dsl_part, dict):
            for expression in dsl_part.values():
                if isinstance(expression, six.string_types):
                    expr.validate(expression)

    def _spec_property(self, prop_name, spec_cls):
        prop_val = self._data.get(prop_name)

        return instantiate_spec(spec_cls, prop_val) if prop_val else None

    def _group_spec(self, spec_cls, *prop_names):
        if not prop_names:
            return None

        data = {}

        for prop_name in prop_names:
            prop_val = self._data.get(prop_name)

            if prop_val:
                data[prop_name] = prop_val

        return instantiate_spec(spec_cls, data)

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

        if isinstance(prop_val, six.string_types):
            return [self._as_tuple(prop_val)]

        return [self._as_tuple(item) for item in prop_val]

    @staticmethod
    def _as_tuple(val):
        return list(val.items())[0] if isinstance(val, dict) else (val, '')

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
            v = v.strip()
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

    def __repr__(self):
        return "%s %s" % (self.__class__.__name__, self.to_dict())


class BaseListSpec(BaseSpec):
    item_class = None

    _schema = {
        "type": "object",
        "properties": {
            "version": types.VERSION
        },
        "additionalProperties": types.NONEMPTY_DICT,
        "required": ["version"],
    }

    def __init__(self, data):
        super(BaseListSpec, self).__init__(data)

        self.items = []

        for k, v in six.iteritems(data):
            if k != 'version':
                v['name'] = k
                self._inject_version([k])
                self.items.append(instantiate_spec(self.item_class, v))

    def validate_schema(self):
        super(BaseListSpec, self).validate_schema()

        if len(self._data.keys()) < 2:
            raise exc.InvalidModelException(
                'At least one item must be in the list [data=%s].' %
                self._data
            )

    def get_items(self):
        return self.items

    def __getitem__(self, idx):
        return self.items[idx]

    def __len__(self):
        return len(self.items)


class BaseSpecList(object):
    item_class = None

    _version = '1.0'

    def __init__(self, data):
        self.items = {}

        for k, v in six.iteritems(data):
            if k != 'version':
                v['name'] = k
                v['version'] = self._version
                self.items[k] = instantiate_spec(self.item_class, v)

    def item_keys(self):
        return self.items.keys()

    def __iter__(self):
        return six.itervalues(self.items)

    def __getitem__(self, name):
        return self.items.get(name)

    def __len__(self):
        return len(self.items)

    def get(self, name):
        return self.__getitem__(name)
