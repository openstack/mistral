# Copyright 2014 - Mirantis, Inc.
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
import re
import six

from mistral import exceptions as exc
from mistral import expressions as expr
from mistral import utils
from mistral.workbook import types
from mistral.workbook.v2 import base
from mistral.workbook.v2 import policies


WITH_ITEMS_PTRN = re.compile(
    "\s*([\w\d_\-]+)\s*in\s*(\[.+\]|%s)" % expr.INLINE_YAQL_REGEXP
)
RESERVED_TASK_NAMES = [
    'noop',
    'fail',
    'succeed',
    'pause'
]


class TaskSpec(base.BaseSpec):
    # See http://json-schema.org
    _polymorphic_key = ('type', 'direct')

    _schema = {
        "type": "object",
        "properties": {
            "type": types.WORKFLOW_TYPE,
            "action": types.NONEMPTY_STRING,
            "workflow": types.NONEMPTY_STRING,
            "input": types.NONEMPTY_DICT,
            "with-items": {
                "oneOf": [
                    types.NONEMPTY_STRING,
                    types.UNIQUE_STRING_LIST
                ]
            },
            "publish": types.NONEMPTY_DICT,
            "retry": policies.RETRY_SCHEMA,
            "wait-before": policies.WAIT_BEFORE_SCHEMA,
            "wait-after": policies.WAIT_AFTER_SCHEMA,
            "timeout": policies.TIMEOUT_SCHEMA,
            "pause-before": policies.PAUSE_BEFORE_SCHEMA,
            "concurrency": policies.CONCURRENCY_SCHEMA,
            "target": types.NONEMPTY_STRING,
            "keep-result": types.YAQL_OR_BOOLEAN,
            "safe-rerun": types.YAQL_OR_BOOLEAN
        },
        "additionalProperties": False,
        "anyOf": [
            {
                "not": {
                    "type": "object",
                    "required": ["action", "workflow"]
                },
            },
            {
                "oneOf": [
                    {
                        "type": "object",
                        "required": ["action"]
                    },
                    {
                        "type": "object",
                        "required": ["workflow"]
                    }
                ]
            }
        ]
    }

    def __init__(self, data):
        super(TaskSpec, self).__init__(data)

        self._name = data['name']
        self._description = data.get('description')
        self._action = data.get('action')
        self._workflow = data.get('workflow')
        self._input = data.get('input', {})
        self._with_items = self._transform_with_items()
        self._publish = data.get('publish', {})
        self._policies = self._group_spec(
            policies.PoliciesSpec,
            'retry',
            'wait-before',
            'wait-after',
            'timeout',
            'pause-before',
            'concurrency'
        )
        self._target = data.get('target')
        self._keep_result = data.get('keep-result', True)
        self._safe_rerun = data.get('safe-rerun', False)

        self._process_action_and_workflow()

    def validate_schema(self):
        super(TaskSpec, self).validate_schema()

        action = self._data.get('action')
        workflow = self._data.get('workflow')

        # Validate YAQL expressions.
        if action or workflow:
            inline_params = self._parse_cmd_and_input(action or workflow)[1]
            self.validate_yaql_expr(inline_params)

        self.validate_yaql_expr(self._data.get('input', {}))
        self.validate_yaql_expr(self._data.get('publish', {}))
        self.validate_yaql_expr(self._data.get('keep-result', {}))
        self.validate_yaql_expr(self._data.get('safe-rerun', {}))

    def _transform_with_items(self):
        raw = self._data.get('with-items', [])
        with_items = {}

        if isinstance(raw, six.string_types):
            raw = [raw]

        for item in raw:
            if not isinstance(item, six.string_types):
                raise exc.InvalidModelException("'with-items' elements should"
                                                " be strings: %s" % self._data)

            match = re.match(WITH_ITEMS_PTRN, item)

            if not match:
                msg = ("Wrong format of 'with-items' property. Please use "
                       "format 'var in {[some, list] | <%% $.array %%> }: "
                       "%s" % self._data)
                raise exc.InvalidModelException(msg)

            var_name, array = match.groups()

            # Validate YAQL expression that may follow after "in" for the
            # with-items syntax "var in {[some, list] | <% $.array %> }".
            self.validate_yaql_expr(array)

            if array.startswith('['):
                try:
                    array = json.loads(array)
                except Exception as e:
                    msg = ("Invalid array in 'with-items' clause: "
                           "%s, error: %s" % (array, str(e)))
                    raise exc.InvalidModelException(msg)

            with_items[var_name] = array

        return with_items

    def _process_action_and_workflow(self):
        params = {}

        if self._action:
            self._action, params = self._parse_cmd_and_input(self._action)
        elif self._workflow:
            self._workflow, params = self._parse_cmd_and_input(
                self._workflow)
        else:
            self._action = 'std.noop'

        utils.merge_dicts(self._input, params)

    def get_name(self):
        return self._name

    def get_description(self):
        return self._description

    def get_type(self):
        return self._type

    def get_action_name(self):
        return self._action if self._action else None

    def get_workflow_name(self):
        return self._workflow

    def get_input(self):
        return self._input

    def get_with_items(self):
        return self._with_items

    def get_policies(self):
        return self._policies

    def get_target(self):
        return self._target

    def get_publish(self):
        return self._publish

    def get_keep_result(self):
        return self._keep_result

    def get_safe_rerun(self):
        return self._safe_rerun


class DirectWorkflowTaskSpec(TaskSpec):
    _polymorphic_value = 'direct'

    _on_clause_type = {
        "oneOf": [
            types.NONEMPTY_STRING,
            types.UNIQUE_STRING_OR_YAQL_CONDITION_LIST
        ]
    }

    _direct_workflow_schema = {
        "type": "object",
        "properties": {
            "type": {"enum": [_polymorphic_value]},
            "join": {
                "oneOf": [
                    {"enum": ["all", "one"]},
                    types.POSITIVE_INTEGER
                ]
            },
            "on-complete": _on_clause_type,
            "on-success": _on_clause_type,
            "on-error": _on_clause_type
        }
    }

    _schema = utils.merge_dicts(copy.deepcopy(TaskSpec._schema),
                                _direct_workflow_schema)

    def __init__(self, data):
        super(DirectWorkflowTaskSpec, self).__init__(data)

        self._join = data.get('join')
        self._on_complete = self.prepare_on_clause(
            self._as_list_of_tuples('on-complete')
        )
        self._on_success = self.prepare_on_clause(
            self._as_list_of_tuples('on-success')
        )
        self._on_error = self.prepare_on_clause(
            self._as_list_of_tuples('on-error')
        )

    def validate_schema(self):
        super(DirectWorkflowTaskSpec, self).validate_schema()

        # Validate YAQL expressions.
        self._validate_transitions('on-complete')
        self._validate_transitions('on-success')
        self._validate_transitions('on-error')

    def _validate_transitions(self, on_clause):
        val = self._data.get(on_clause, [])

        [self.validate_yaql_expr(t)
         for t in ([val] if isinstance(val, six.string_types) else val)]

    @staticmethod
    def prepare_on_clause(list_of_tuples):
        for i, task in enumerate(list_of_tuples):
            task_name, params = DirectWorkflowTaskSpec._parse_cmd_and_input(
                task[0]
            )
            list_of_tuples[i] = (task_name, task[1], params)

        return list_of_tuples

    def get_join(self):
        return self._join

    def get_on_complete(self):
        return self._on_complete

    def get_on_success(self):
        return self._on_success

    def get_on_error(self):
        return self._on_error


class ReverseWorkflowTaskSpec(TaskSpec):
    _polymorphic_value = 'reverse'

    _reverse_workflow_schema = {
        "type": "object",
        "properties": {
            "type": {"enum": [_polymorphic_value]},
            "requires": {
                "oneOf": [types.NONEMPTY_STRING, types.UNIQUE_STRING_LIST]
            }
        }
    }

    _schema = utils.merge_dicts(copy.deepcopy(TaskSpec._schema),
                                _reverse_workflow_schema)

    def __init__(self, data):
        super(ReverseWorkflowTaskSpec, self).__init__(data)

        self._requires = data.get('requires', [])

    def get_requires(self):
        if isinstance(self._requires, six.string_types):
            return [self._requires]

        return self._requires


class TaskSpecList(base.BaseSpecList):
    item_class = TaskSpec
