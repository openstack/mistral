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

#TODO(rakhmerov): Remove this module after refactoring.

import copy

from mistral.engine.actions import actions
from mistral.engine.actions import action_types
from mistral.engine.actions import action_helper as a_h
from mistral.engine import data_flow as df
import mistral.exceptions as exc
from mistral.workbook import services
from mistral.workbook import tasks


def create_action(db_task):
    action_type = a_h.get_action_type(db_task)
    context = db_task.get('in_context')
    task_spec = tasks.TaskSpec(df.apply_context(
        copy.copy(db_task['task_spec']), context))
    service_spec = services.ServiceSpec(df.apply_context(
        copy.copy(db_task['service_spec']), context))

    if not action_types.is_valid(action_type):
        raise exc.InvalidActionException("Action type is not supported: %s" %
                                         action_type)

    action = _get_mapping()[action_type](db_task, task_spec, service_spec)
    action.result_helper = _find_action_result_helper(db_task, action)
    return action


def _get_mapping():
    return {
        action_types.ECHO: get_echo_action,
        action_types.REST_API: get_rest_action,
        action_types.MISTRAL_REST_API: get_mistral_rest_action,
        action_types.OSLO_RPC: get_amqp_action,
        action_types.SEND_EMAIL: get_send_email_action,
        action_types.SSH: get_ssh_action
    }


def _find_action_result_helper(task, action):
    try:
        return task['service_spec']['actions'][action.name].get('output', {})
    except (KeyError, AttributeError):
        return {}


def get_echo_action(db_task, task, service):
    action_type = service.type
    action_name = task.get_action_name()

    output = service.actions.get(action_name).output

    return actions.EchoAction(action_type, action_name, output=output)


def get_rest_action(db_task, task, service):
    action_type = service.type
    action_name = task.get_action_name()
    action = service.actions.get(action_name)
    task_params = task.parameters
    url = service.parameters['baseUrl'] +\
        action.parameters['url']

    headers = {}
    headers.update(task.get_property('headers', {}))
    headers.update(action.to_dict().get('headers', {}))

    method = action.parameters.get('method', "GET")

    # input_yaql = task.get('input')
    # TODO(nmakhotkin) extract input from context with the YAQL expression
    params = {}  # expressions.evaluate(input_expr, ctx)
    data = {}

    if method.upper() == "GET":
        params.update(task_params)
    elif method.upper() in ["POST", "PUT"]:
        data.update(task_params)

    return actions.RestAction(action_type, action_name, url,
                              params=params, method=method,
                              headers=headers, data=data)


def get_mistral_rest_action(db_task, task, service):
    mistral_headers = {
        'Mistral-Workbook-Name': db_task['workbook_name'],
        'Mistral-Execution-Id': db_task['execution_id'],
        'Mistral-Task-Id': db_task['id'],
    }

    action = get_rest_action(db_task, task, service)
    action.headers.update(mistral_headers)

    return action


def get_amqp_action(db_task, task, service):
    action_type = service.type
    action_name = task.get_action_name()
    action = service.actions.get(action_name)
    action_params = action.parameters
    task_params = task.parameters
    service_parameters = service.parameters

    host = service_parameters['host']
    port = service_parameters.get('port')
    userid = service_parameters['userid']
    password = service_parameters['password']
    virtual_host = action_params['virtual_host']
    message = task_params['message']
    routing_key = task_params.get('routing_key', None)
    exchange = action_params.get('exchange')
    queue_name = action_params['queue_name']

    return actions.OsloRPCAction(action_type, action_name, host, userid,
                                 password, virtual_host, message, routing_key,
                                 port, exchange, queue_name)


def get_send_email_action(db_task, task, service):
    #TODO(dzimine): Refactor action_type and action_name settings
    #               for all actions
    action_type = service.type
    action_name = task.get_action_name()
    task_params = task.parameters
    service_params = service.parameters

    return actions.SendEmailAction(action_type, action_name,
                                   task_params, service_params)


def get_ssh_action(db_task, task, service):
    action_type = service.type
    action_name = task.get_action_name()
    task_params = task.parameters
    action = service.actions.get(action_name)
    action_params = action.parameters

    # Merge/replace action_params by task_params.
    all_params = copy.copy(action_params)
    all_params.update(task_params)

    cmd = all_params['cmd']
    host = all_params['host']
    username = all_params['username']
    password = all_params['password']

    return actions.SSHAction(action_type, action_name, cmd,
                             host, username, password)
