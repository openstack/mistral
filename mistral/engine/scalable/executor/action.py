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

import requests
from mistral.engine.scalable.executor import action_types
import mistral.exceptions as exc
from mistral.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def create_action(task):
    action_type = task['service_dsl']['type']
    action_name = task['task_dsl']['action'].split(':')[1]
    action_params = task['service_dsl']['actions'][action_name]['parameters']
    task_params = task['task_dsl'].get('parameters', None)

    if action_type == action_types.REST_API:
        url = task['service_dsl']['parameters']['baseUrl'] +\
            action_params['url']

        headers = {
            'Mistral-Workbook-Name': task['workbook_name'],
            'Mistral-Execution-Id': task['execution_id'],
            'Mistral-Task-Id': task['id'],
        }

        return RestAction(url=url,
                          params=task_params,
                          method=action_params['method'],
                          headers=headers)
    else:
        raise exc.InvalidActionException("Action type is not supported: %s" %
                                         action_type)


class BaseAction(object):
    def do_action(self):
        pass


class RestAction(BaseAction):
    def __init__(self, url, params={}, method="GET", headers=None):
        self.url = url
        self.params = params
        self.method = method
        self.headers = headers

    def do_action(self):
        LOG.info("Sending action HTTP request "
                 "[method=%s, url=%s, params=%s, headers=%s]" %
                 (self.method, self.url, self.params, self.headers))
        resp = requests.request(self.method, self.url, params=self.params,
                                headers=self.headers)
        LOG.info("Received HTTP response:\n%s\n%s" %
                 (resp.status_code, resp.content))


# TODO(rakhmerov): add other types of actions.
