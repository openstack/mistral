# Copyright 2015 - Mirantis, Inc.
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

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.workbook import parser as spec_parser


def create_actions(definition, scope='private'):
    action_list_spec = spec_parser.get_action_list_spec_from_yaml(definition)

    db_actions = []

    for action_spec in action_list_spec.get_actions():
        db_actions.append(create_action(action_spec, definition, scope))

    return db_actions


def update_actions(definition, scope='private', identifier=None):
    action_list_spec = spec_parser.get_action_list_spec_from_yaml(definition)
    actions = action_list_spec.get_actions()

    if identifier and len(actions) > 1:
        raise exc.InputException(
            "More than one actions are not supported for "
            "update with identifier. [identifier: %s]" %
            identifier
        )

    db_actions = []

    for action_spec in action_list_spec.get_actions():
        db_actions.append(update_action(
            action_spec,
            definition,
            scope,
            identifier=identifier
        ))

    return db_actions


def create_or_update_actions(definition, scope='private'):
    action_list_spec = spec_parser.get_action_list_spec_from_yaml(definition)

    db_actions = []

    for action_spec in action_list_spec.get_actions():
        db_actions.append(
            create_or_update_action(action_spec, definition, scope)
        )

    return db_actions


def create_action(action_spec, definition, scope):
    return db_api.create_action_definition(
        _get_action_values(action_spec, definition, scope)
    )


def update_action(action_spec, definition, scope, identifier=None):
    action = db_api.load_action_definition(action_spec.get_name())

    if action and action.is_system:
        raise exc.InvalidActionException(
            "Attempt to modify a system action: %s" %
            action.name
        )

    values = _get_action_values(action_spec, definition, scope)

    return db_api.update_action_definition(
        identifier if identifier else values['name'],
        values
    )


def create_or_update_action(action_spec, definition, scope):
    action = db_api.load_action_definition(action_spec.get_name())

    if action and action.is_system:
        raise exc.InvalidActionException(
            "Attempt to modify a system action: %s" %
            action.name
        )

    values = _get_action_values(action_spec, definition, scope)

    return db_api.create_or_update_action_definition(values['name'], values)


def get_input_list(action_input):
    input_list = []

    for param in action_input:
        if isinstance(param, dict):
            for k, v in param.items():
                input_list.append("%s=%s" % (k, json.dumps(v)))
        else:
            input_list.append(param)

    return input_list


def _get_action_values(action_spec, definition, scope):
    action_input = action_spec.to_dict().get('input', [])
    input_list = get_input_list(action_input)

    values = {
        'name': action_spec.get_name(),
        'description': action_spec.get_description(),
        'tags': action_spec.get_tags(),
        'definition': definition,
        'spec': action_spec.to_dict(),
        'is_system': False,
        'input': ", ".join(input_list) if input_list else None,
        'scope': scope
    }

    return values
