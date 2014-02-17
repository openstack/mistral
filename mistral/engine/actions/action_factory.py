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

from mistral.engine.actions import actions
from mistral.engine.actions import action_types
from mistral.engine.actions import action_helper as a_h
import mistral.exceptions as exc


def create_action(task):
    action_type = a_h.get_action_type(task)

    if not action_types.is_valid(action_type):
        raise exc.InvalidActionException("Action type is not supported: %s" %
                                         action_type)

    action = _get_mapping()[action_type](task)
    action.result_helper = _find_action_result_helper(task, action)
    return action


def _get_mapping():
    return {
        action_types.REST_API: get_rest_action,
        action_types.MISTRAL_REST_API: get_mistral_rest_action,
        action_types.OSLO_RPC: get_amqp_action,
        action_types.SEND_EMAIL: get_send_email_action
    }


def _find_action_result_helper(task, action):
    try:
        return task['service_dsl']['actions'][action.name].get('output')
    except (KeyError, AttributeError):
        return None


def get_rest_action(task):
    action_type = a_h.get_action_type(task)
    action_name = task['task_dsl']['action'].split(':')[1]
    action_dsl = task['service_dsl']['actions'][action_name]
    task_params = task['task_dsl'].get('parameters', {})
    url = task['service_dsl']['parameters']['baseUrl'] +\
        action_dsl['parameters']['url']

    headers = {}
    headers.update(task['task_dsl'].get('headers', {}))
    headers.update(action_dsl.get('headers', {}))

    method = action_dsl['parameters'].get('method', "GET")

    # input_yaql = task.get('input')
    # TODO(nmakhotkin) extract input from context within the YAQL expression
    task_input = {}  # yaql_utils.evaluate(input_yaql, ctx)
    task_data = {}

    if method.upper() == "GET":
        task_params.update(task_input)
    elif method.upper() in ["POST", "PUT"]:
        task_data.update(task_input)

    return actions.RestAction(action_type, action_name, url,
                              params=task_params, method=method,
                              headers=headers, data=task_data)


def get_mistral_rest_action(task):
    mistral_headers = {
        'Mistral-Workbook-Name': task['workbook_name'],
        'Mistral-Execution-Id': task['execution_id'],
        'Mistral-Task-Id': task['id'],
    }

    action = get_rest_action(task)
    action.headers.update(mistral_headers)

    return action


def get_amqp_action(task):
    action_type = a_h.get_action_type(task)
    action_name = task['task_dsl']['action'].split(':')[1]
    action_params = task['service_dsl']['actions'][action_name]['parameters']
    task_params = task['task_dsl'].get('parameters', {})
    service_parameters = task['service_dsl'].get('parameters', {})

    host = service_parameters['host']
    port = service_parameters.get('port')
    userid = service_parameters['userid']
    password = service_parameters['password']
    virtual_host = action_params['virtual_host']
    message = task_params['message']
    routing_key = task_params.get('routing_key', None)
    exchange = action_params.get('exchange')
    queue_name = action_params['queue_name']

    return actions.OsloRPCAction(action_type, host, userid, password,
                                 virtual_host, message, routing_key, port,
                                 exchange, queue_name)


def get_send_email_action(task):
    #TODO(dzimine): Refactor action_type and action_name settings
    #               for all actions
    action_type = a_h.get_action_type(task)
    action_name = task['task_dsl']['action'].split(':')[1]
    task_params = task['task_dsl'].get('parameters', {})
    service_params = task['service_dsl'].get('parameters', {})

    return actions.SendEmailAction(action_type, action_name,
                                   task_params, service_params)
