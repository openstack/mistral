# Copyright 2014 - Mirantis, Inc.
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
import re
import six

from mistral import exceptions as exc
from mistral import utils
from mistral.workbook import base
from mistral.workbook.v2 import task_policies


WITH_ITEMS_PTRN = re.compile(
    "\s*([\w\d_\-]+)\s*in\s*(\[.+\]|%s)" % base.INLINE_YAQL
)


class TaskSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "name": {"type": "string"},
            "description": {"type": "string"},
            "action": {"type": ["string", "null"]},
            "workflow": {"type": ["string", "null"]},
            "input": {"type": ["object", "null"]},
            "with-items": {"type": ["string", "array", "null"]},
            "publish": {"type": ["object", "null"]},
            "policies": {"type": ["object", "null"]},
            "target": {"type": ["string", "null"]},
        },
        "required": ["version", "name"],
    }

    _version = '2.0'

    def __init__(self, data):
        super(TaskSpec, self).__init__(data)

        self._name = data['name']
        self._description = data.get('description')
        self._action = data.get('action')
        self._workflow = data.get('workflow')
        self._input = data.get('input', {})
        self._with_items = self._transform_with_items()
        self._publish = data.get('publish', {})
        self._policies = self._spec_property(
            'policies',
            task_policies.TaskPoliciesSpec
        )
        self._target = data.get('target')

        self._process_action_and_workflow()

    def validate(self):
        super(TaskSpec, self).validate()

        action = self._data.get('action')
        workflow = self._data.get('workflow')

        if action and workflow:
            msg = ("Task properties 'action' and 'workflow' can't be"
                   " specified both: %s" % self._data)
            raise exc.InvalidModelException(msg)

        self._transform_with_items()

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


class DirectWorkflowTaskSpec(TaskSpec):
    _direct_props = {
        "properties": {
            "join": {"type": ["string", "integer"]},
            "on-complete": {"type": ["array", "null"]},
            "on-success": {"type": ["array", "null"]},
            "on-error": {"type": ["array", "null"]}
        },
        "additionalProperties": False
    }

    _schema = utils.merge_dicts(copy.deepcopy(TaskSpec._schema),
                                _direct_props)

    def __init__(self, data):
        super(DirectWorkflowTaskSpec, self).__init__(data)

        self._join = data.get('join')
        self._on_complete = self._as_list_of_tuples('on-complete')
        self._on_success = self._as_list_of_tuples('on-success')
        self._on_error = self._as_list_of_tuples('on-error')

    def validate(self):
        super(DirectWorkflowTaskSpec, self).validate()

        if 'join' in self._data:
            join = self._data.get('join')

            if not (isinstance(join, int) or join in ['all', 'one']):
                msg = ("Task property 'join' is only allowed to be an"
                       " integer, 'all' or 'one': %s" % self._data)
                raise exc.InvalidModelException(msg)

    def get_join(self):
        return self._join

    def get_on_complete(self):
        return self._on_complete

    def get_on_success(self):
        return self._on_success

    def get_on_error(self):
        return self._on_error


class ReverseWorkflowTaskSpec(TaskSpec):
    _reverse_props = {
        "properties": {
            "requires": {"type": ["string", "array", "null"]}
        },
        "additionalProperties": False
    }

    _schema = utils.merge_dicts(copy.deepcopy(TaskSpec._schema),
                                _reverse_props)

    def __init__(self, data):
        super(ReverseWorkflowTaskSpec, self).__init__(data)

        self._requires = data.get('requires', [])

    def get_requires(self):
        if isinstance(self._requires, six.string_types):
            return [self._requires]

        return self._requires


class TaskSpecList(base.BaseSpecList):
    item_class = TaskSpec
    _version = '2.0'

    @staticmethod
    def get_class(wf_type):
        """Gets a task specification list class by given workflow type.

        :param wf_type: Workflow type
        :returns: Task specification list class
        """
        for spec_list_cls in utils.iter_subclasses(TaskSpecList):
            if wf_type == spec_list_cls.__type__:
                return spec_list_cls

        msg = ("Can not find task list specification with workflow type:"
               " %s" % wf_type)
        raise exc.NotFoundException(msg)


class DirectWfTaskSpecList(TaskSpecList):
    __type__ = 'direct'
    item_class = DirectWorkflowTaskSpec


class ReverseWfTaskSpecList(TaskSpecList):
    __type__ = 'reverse'
    item_class = ReverseWorkflowTaskSpec
