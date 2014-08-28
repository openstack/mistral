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

import re
import six

from mistral import exceptions as exc
from mistral import utils
from mistral.workbook import base
from mistral.workbook.v2 import retry

# TODO(rakhmerov): In progress.

CMD_PTRN = re.compile("^[\w\.]+[^=\s\"]*")
PARAMS_PTRN = re.compile("([\w]+)=(\"[^=]*\"|\'[^=]*'|[\d\.]*)")


class TaskSpec(base.BaseSpec):
    # See http://json-schema.org
    _schema = {
        "type": "object",
        "properties": {
            "Version": {"type": "string"},
            "name": {"type": "string"},
            "action": {"type": ["string", "null"]},
            "workflow": {"type": ["string", "null"]},
            "workflow-parameters": {"type": ["object", "null"]},
            "parameters": {"type": ["object", "null"]},
            "publish": {"type": ["object", "null"]},
            "retry": {"type": ["object", "null"]},
            "requires": {"type": ["string", "array", "null"]},
            "on-finish": {"type": ["string", "object", "array", "null"]},
            "on-success": {"type": ["string", "object", "array", "null"]},
            "on-error": {"type": ["string", "object", "array", "null"]}
        },
        "required": ["Version", "name"],
        "additionalProperties": False
    }

    _version = '2.0'

    def __init__(self, data):
        super(TaskSpec, self).__init__(data)

        self._name = data['name']
        self._action = data.get('action')
        self._workflow = data.get('workflow')
        self._workflow_parameters = data.get('workflow-parameters')
        self._parameters = data.get('parameters', {})
        self._publish = data.get('publish', {})
        self._retry = self._spec_property('retry', retry.RetrySpec)
        self._requires = data.get('requires', [])

        self._process_action_and_workflow()

    def _process_action_and_workflow(self):
        if self._action and self._workflow:
            msg = "Task properties 'action' and 'workflow' can't be" \
                  " specified both:" % self._data
            raise exc.InvalidModelException(msg)

        if not self._action and not self._workflow:
            msg = "One of task properties 'action' or 'workflow' must be" \
                  " specified:" % self._data
            raise exc.InvalidModelException(msg)

        if self._action:
            self._action, params = self._parse_cmd_and_params(self._action)
        elif self._workflow:
            self._workflow, params = self._parse_cmd_and_params(self._workflow)

        utils.merge_dicts(self._parameters, params)

    def _parse_cmd_and_params(self, cmd_str):
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

            params[k] = v

        return cmd, params

    def get_name(self):
        return self._name

    def get_action_name(self):
        return self._action if self._action else None

    def get_action_namespace(self):
        if not self._action:
            return None

        arr = self._action.split('.')

        return arr[0] if len(arr) > 1 else None

    def get_short_action_name(self):
        return self._action.split('.')[-1] if self._action else None

    def get_workflow_name(self):
        return self._workflow

    def get_workflow_namespace(self):
        if not self._workflow:
            return None

        arr = self._workflow.split('.')

        return arr[0] if len(arr) > 1 else None

    def get_short_workflow_name(self):
        return self._workflow.split('.')[-1] if self._workflow else None

    def get_workflow_parameters(self):
        return self._workflow_parameters

    def get_parameters(self):
        return self._parameters

    def get_retry(self):
        return self._retry

    def get_publish(self):
        return self._publish

    def get_requires(self):
        if isinstance(self._requires, six.string_types):
            return [self._requires]

        return self._requires

    def get_on_finish(self):
        return self._get_as_dict("on-finish")

    def get_on_success(self):
        return self._get_as_dict("on-success")

    def get_on_error(self):
        return self._get_as_dict("on-error")


class TaskSpecList(base.BaseSpecList):
    item_class = TaskSpec
    _version = '2.0'
