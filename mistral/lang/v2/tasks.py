# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2019 - NetCracker Technology Corp.
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

from mistral import exceptions as exc
from mistral import expressions
from mistral.lang import types
from mistral.lang.v2 import base
from mistral.lang.v2 import on_clause
from mistral.lang.v2 import policies
from mistral.lang.v2 import publish
from mistral.lang.v2 import retry_policy
from mistral.workflow import states
from mistral_lib import utils

# Task types.
ACTION_TASK_TYPE = 'ACTION'
WORKFLOW_TASK_TYPE = 'WORKFLOW'


_expr_ptrns = [expressions.patterns[name] for name in expressions.patterns]

WITH_ITEMS_PTRN = re.compile(
    r"\s*([\w\d_\-]+)\s*in\s*(\[.+\]|%s)" % '|'.join(_expr_ptrns)
)

MAX_LENGTH_TASK_NAME = 255
# Length of a join task name must be less than or equal to maximum
# of task_executions unique_key and named_locks name. Their
# maximum equals 255.
# https://dev.mysql.com/doc/refman/5.6/en/innodb-restrictions.html
# For example: "join-task-" + "workflow execution id" + "-" +
# "task join name" = 255
# "task join name" = 255 - 36 - 1 - 10 = MAX_LENGTH_TASK_NAME - 47
MAX_LENGTH_JOIN_TASK_NAME = MAX_LENGTH_TASK_NAME - 47


class TaskSpec(base.BaseSpec):
    # See http://json-schema.org
    _polymorphic_key = ('type', 'direct')

    _schema = {
        "type": "object",
        "properties": {
            "type": types.WORKFLOW_TYPE,
            "action": types.NONEMPTY_STRING,
            "workflow": types.NONEMPTY_STRING,
            "input": {
                "oneOf": [
                    types.NONEMPTY_DICT,
                    types.NONEMPTY_STRING
                ]
            },
            "with-items": {
                "oneOf": [
                    types.NONEMPTY_STRING,
                    types.UNIQUE_STRING_LIST
                ]
            },
            "publish": types.NONEMPTY_DICT,
            "publish-on-error": types.NONEMPTY_DICT,
            "publish-on-skip": types.NONEMPTY_DICT,
            "retry": retry_policy.RetrySpec.get_schema(),
            "wait-before": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "wait-after": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "timeout": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "pause-before": types.EXPRESSION_OR_BOOLEAN,
            "concurrency": types.EXPRESSION_OR_POSITIVE_INTEGER,
            "fail-on": types.EXPRESSION_OR_BOOLEAN,
            "target": types.NONEMPTY_STRING,
            "keep-result": types.EXPRESSION_OR_BOOLEAN,
            "safe-rerun": types.EXPRESSION_OR_BOOLEAN
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

    def __init__(self, data, validate):
        super(TaskSpec, self).__init__(data, validate)

        self._name = data['name']
        self._description = data.get('description')
        self._action = data.get('action')
        self._workflow = data.get('workflow')
        self._tags = data.get('tags', [])
        self._input = data.get('input', {})
        self._with_items = self._get_with_items_as_dict()
        self._publish = data.get('publish', {})
        self._publish_on_error = data.get('publish-on-error', {})
        self._publish_on_skip = data.get('publish-on-skip', {})
        self._policies = self._group_spec(
            policies.PoliciesSpec,
            'retry',
            'wait-before',
            'wait-after',
            'timeout',
            'pause-before',
            'concurrency',
            'fail-on'
        )
        self._target = data.get('target')
        self._keep_result = data.get('keep-result', True)
        self._safe_rerun = data.get('safe-rerun')

        self._process_action_and_workflow()

    def validate_schema(self):
        super(TaskSpec, self).validate_schema()

        self._validate_name()

        action = self._data.get('action')
        workflow = self._data.get('workflow')

        # Validate YAQL expressions.
        if action or workflow:
            inline_params = self._parse_cmd_and_input(action or workflow)[1]
            self.validate_expr(inline_params)

        self.validate_expr(self._data.get('input', {}))
        self.validate_expr(self._data.get('publish', {}))
        self.validate_expr(self._data.get('publish-on-error', {}))
        self.validate_expr(self._data.get('publish-on-skip', {}))
        self.validate_expr(self._data.get('keep-result', {}))
        self.validate_expr(self._data.get('safe-rerun', {}))

    def _validate_name(self):
        task_name = self._data.get('name')

        if len(task_name) > MAX_LENGTH_TASK_NAME:
            raise exc.InvalidModelException(
                "The length of a '{0}' task name must not exceed {1}"
                " symbols".format(task_name, MAX_LENGTH_TASK_NAME))

    def _get_with_items_as_dict(self):
        raw = self._data.get('with-items', [])

        with_items = {}

        if isinstance(raw, str):
            raw = [raw]

        for item in raw:
            if not isinstance(item, str):
                raise exc.InvalidModelException(
                    "'with-items' elements should be strings: %s" % self._data
                )

            match = re.match(WITH_ITEMS_PTRN, item)

            if not match:
                raise exc.InvalidModelException(
                    "Wrong format of 'with-items' property. Please use "
                    "format 'var in {[some, list] | <%% $.array %%> }: "
                    "%s" % self._data
                )

            match_groups = match.groups()
            var_name = match_groups[0]
            array = match_groups[1]

            # Validate YAQL expression that may follow after "in" for the
            # with-items syntax "var in {[some, list] | <% $.array %> }".
            self.validate_expr(array)

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

    def get_action_name(self):
        return self._action if self._action else None

    def get_workflow_name(self):
        return self._workflow

    def get_tags(self):
        return self._tags

    def get_input(self):
        return self._input

    def get_with_items(self):
        return self._with_items

    def get_policies(self):
        return self._policies

    def get_target(self):
        return self._target

    def get_publish(self, state):
        spec = None

        if state == states.SUCCESS and self._publish:
            spec = publish.PublishSpec(
                {'branch': self._publish},
                validate=self._validate
            )
        elif state == states.ERROR and self._publish_on_error:
            spec = publish.PublishSpec(
                {'branch': self._publish_on_error},
                validate=self._validate
            )
        elif state == states.SKIPPED and self._publish_on_skip:
            spec = publish.PublishSpec(
                {'branch': self._publish_on_skip},
                validate=self._validate
            )
        return spec

    def get_keep_result(self):
        return self._keep_result

    def get_safe_rerun(self):
        return self._safe_rerun

    def get_type(self):
        return (WORKFLOW_TASK_TYPE if self._workflow
                else ACTION_TASK_TYPE)


class DirectWorkflowTaskSpec(TaskSpec):
    _polymorphic_value = 'direct'

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
            "on-complete": on_clause.OnClauseSpec.get_schema(),
            "on-success": on_clause.OnClauseSpec.get_schema(),
            "on-error": on_clause.OnClauseSpec.get_schema(),
            "on-skip": on_clause.OnClauseSpec.get_schema()
        }
    }

    _schema = utils.merge_dicts(
        copy.deepcopy(TaskSpec._schema),
        _direct_workflow_schema
    )

    def __init__(self, data, validate):
        super(DirectWorkflowTaskSpec, self).__init__(data, validate)

        self._join = data.get('join')

        on_spec_cls = on_clause.OnClauseSpec

        self._on_complete = self._spec_property('on-complete', on_spec_cls)
        self._on_success = self._spec_property('on-success', on_spec_cls)
        self._on_error = self._spec_property('on-error', on_spec_cls)
        self._on_skip = self._spec_property('on-skip', on_spec_cls)

    def validate_semantics(self):
        # Validate YAQL expressions.
        self._validate_transitions(self._on_complete)
        self._validate_transitions(self._on_success)
        self._validate_transitions(self._on_error)
        self._validate_transitions(self._on_skip)

        if self._join:
            join_task_name = self.get_name()

            if len(join_task_name) > MAX_LENGTH_JOIN_TASK_NAME:
                raise exc.InvalidModelException(
                    "The length of a '{0}' join task name must not exceed {1} "
                    "symbols".format(join_task_name, MAX_LENGTH_JOIN_TASK_NAME)
                )

    def _validate_transitions(self, on_clause_spec):
        val = on_clause_spec.get_next() if on_clause_spec else []

        if not val:
            return

        [self.validate_expr(t)
            for t in ([val] if isinstance(val, str) else val)]

    def get_publish(self, state):
        spec = super(DirectWorkflowTaskSpec, self).get_publish(state)

        if self._on_complete and self._on_complete.get_publish():
            if spec:
                spec.merge(self._on_complete.get_publish())
            else:
                spec = self._on_complete.get_publish()

        if state == states.SUCCESS:
            on_clause = self._on_success
        elif state == states.ERROR:
            on_clause = self._on_error
        elif state == states.SKIPPED:
            on_clause = self._on_skip

        if on_clause and on_clause.get_publish():
            if spec:
                on_clause.get_publish().merge(spec)

            return on_clause.get_publish()

        return spec

    def get_join(self):
        return self._join

    def get_on_complete(self):
        return self._on_complete

    def get_on_success(self):
        return self._on_success

    def get_on_error(self):
        return self._on_error

    def get_on_skip(self):
        return self._on_skip


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

    _schema = utils.merge_dicts(
        copy.deepcopy(TaskSpec._schema),
        _reverse_workflow_schema
    )

    def __init__(self, data, validate):
        super(ReverseWorkflowTaskSpec, self).__init__(data, validate)

        self._requires = data.get('requires', [])

    def get_requires(self):
        if isinstance(self._requires, str):
            return [self._requires]

        return self._requires


class TaskSpecList(base.BaseSpecList):
    item_class = TaskSpec
