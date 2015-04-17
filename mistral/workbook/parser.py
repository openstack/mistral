# Copyright 2013 - Mirantis, Inc.
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

import yaml
from yaml import error

from mistral import exceptions as exc
from mistral.workbook.v2 import actions as actions_v2
from mistral.workbook.v2 import tasks as tasks_v2
from mistral.workbook.v2 import workbook as wb_v2
from mistral.workbook.v2 import workflows as wf_v2

V2_0 = '2.0'

ALL_VERSIONS = [V2_0]


def parse_yaml(text):
    """Loads a text in YAML format as dictionary object.

    :param text: YAML text.
    :return: Parsed YAML document as dictionary.
    """

    try:
        return yaml.safe_load(text) or {}
    except error.YAMLError as e:
        raise exc.DSLParsingException(
            "Definition could not be parsed: %s\n" % e
        )


def _get_spec_version(spec_dict):
    # If version is not specified it will '2.0' by default.
    ver = V2_0

    if 'version' in spec_dict:
        ver = spec_dict['version']

    if not ver or str(float(ver)) not in ALL_VERSIONS:
        raise exc.DSLParsingException('Unsupported DSL version: %s' % ver)

    return ver


# Factory methods to get specifications either from raw YAML formatted text or
# from dictionaries parsed from YAML formatted text.


def get_workbook_spec(spec_dict):
    if _get_spec_version(spec_dict) == V2_0:
        return wb_v2.WorkbookSpec(spec_dict)

    return None


def get_workbook_spec_from_yaml(text):
    return get_workbook_spec(parse_yaml(text))


def get_action_spec(spec_dict):
    if _get_spec_version(spec_dict) == V2_0:
        return actions_v2.ActionSpec(spec_dict)

    return None


def get_action_spec_from_yaml(text, action_name):
    spec_dict = parse_yaml(text)

    spec_dict['name'] = action_name

    return get_action_spec(spec_dict)


def get_action_list_spec(spec_dict):
    return actions_v2.ActionListSpec(spec_dict)


def get_action_list_spec_from_yaml(text):
    return get_action_list_spec(parse_yaml(text))


def get_workflow_spec(spec_dict):
    if _get_spec_version(spec_dict) == V2_0:
        return wf_v2.WorkflowSpec(spec_dict)

    return None


def get_workflow_list_spec(spec_dict):
    return wf_v2.WorkflowListSpec(spec_dict)


def get_workflow_spec_from_yaml(text):
    return get_workflow_spec(parse_yaml(text))


def get_workflow_list_spec_from_yaml(text):
    return get_workflow_list_spec(parse_yaml(text))


def get_task_spec(spec_dict):
    if _get_spec_version(spec_dict) == V2_0:
        workflow_type = spec_dict.get('type')

        if workflow_type == 'direct':
            return tasks_v2.DirectWorkflowTaskSpec(spec_dict)
        elif workflow_type == 'reverse':
            return tasks_v2.ReverseWorkflowTaskSpec(spec_dict)
        else:
            raise Exception('Unsupported workflow type "%s".' % workflow_type)

    return None
