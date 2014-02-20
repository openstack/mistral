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

from mistral.engine.actions import action_types as a_t
from mistral import exceptions as exc
from mistral.engine import states
from mistral.engine import expressions as expr


def get_action_type(task):
    return task['service_dsl']['type']


def is_task_synchronous(task):
    return get_action_type(task) != a_t.MISTRAL_REST_API


def extract_state_result(action, action_result):
    # All non-Mistral tasks are sync-auto because service doesn't know
    # about Mistral and we need to receive the result immediately.
    if action.type != a_t.MISTRAL_REST_API:
        if action.result_helper.get('select'):
            result = expr.evaluate(action.result_helper['select'],
                                   action_result)
            # TODO(nmakhotkin) get state for other actions
            state = states.get_state_by_http_status_code(action.status)
        else:
            raise exc.InvalidActionException("Cannot get the result of sync "
                                             "task without YAQL expression")

        return state, result
    raise exc.InvalidActionException("Error. Wrong type of action to "
                                     "retrieve the result")
