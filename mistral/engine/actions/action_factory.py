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
import mistral.exceptions as exc


def create_action(task):
    action_type = task['service_dsl']['type']

    if action_type == action_types.REST_API:
        return get_rest_action(task)
    elif action_type == action_types.OSLO_RPC:
        return get_amqp_action(task)
    else:
        raise exc.InvalidActionException("Action type is not supported: %s" %
                                         action_type)


def get_rest_action(task):
    action_name = task['task_dsl']['action'].split(':')[1]
    action_params = task['service_dsl']['actions'][action_name]['parameters']
    task_params = task['task_dsl'].get('parameters', None)
    url = task['service_dsl']['parameters']['baseUrl'] +\
        action_params['url']

    headers = {
        'Mistral-Workbook-Name': task['workbook_name'],
        'Mistral-Execution-Id': task['execution_id'],
        'Mistral-Task-Id': task['id'],
    }

    return actions.RestAction(url=url,
                              params=task_params,
                              method=action_params['method'],
                              headers=headers)


def get_amqp_action(task):
    action_name = task['task_dsl']['action'].split(':')[1]
    action_params = task['service_dsl']['actions'][action_name]['parameters']
    task_params = task['task_dsl'].get('parameters', None)
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

    return actions.OsloRPCAction(host, userid, password, virtual_host,
                                 message, routing_key, port, exchange,
                                 queue_name)
