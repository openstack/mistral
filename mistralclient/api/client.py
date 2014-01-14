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

import six

from keystoneclient.v3 import client as keystone_client

from mistralclient.api import httpclient
from mistralclient.api import workbooks
from mistralclient.api import executions
from mistralclient.api import tasks
from mistralclient.api import listeners


class Client(object):
    def __init__(self, mistral_url=None, username=None, api_key=None,
                 project_name=None, auth_url=None, project_id=None,
                 endpoint_type='publicURL', service_type='workflow',
                 input_auth_token=None):

        (mistral_url,
         token,
         project_id,
         user_id) = self.authenticate(mistral_url, username,
                                      api_key, project_name,
                                      auth_url, project_id,
                                      endpoint_type, service_type,
                                      input_auth_token)

        self.http_client = httpclient.HTTPClient(mistral_url,
                                                 token,
                                                 project_id,
                                                 user_id)
        # Create all resource managers.
        self.workbooks = workbooks.WorkbookManager(self)
        self.executions = executions.ExecutionManager(self)
        self.tasks = tasks.TaskManager(self)
        self.listeners = listeners.ListenerManager(self)

    def authenticate(self, mistral_url=None, username=None, api_key=None,
                     project_name=None, auth_url=None, project_id=None,
                     endpoint_type='publicURL', service_type='workflow',
                     input_auth_token=None):
        if mistral_url and not isinstance(mistral_url, six.string_types):
            raise RuntimeError('Mistral url should be string')
        if (isinstance(project_name, six.string_types) or
                isinstance(project_id, six.string_types)):
            if project_name and project_id:
                raise RuntimeError('Only project name or '
                                   'project id should be set')

            if "v2.0" in auth_url:
                raise RuntimeError('Mistral supports only v3  '
                                   'keystone API.')

            keystone = keystone_client.Client(username=username,
                                              password=api_key,
                                              token=input_auth_token,
                                              tenant_id=project_id,
                                              tenant_name=project_name,
                                              auth_url=auth_url)

            keystone.authenticate()
            token = keystone.auth_token
            user_id = keystone.user_id
            if project_name and not project_id:
                if keystone.tenants.find(name=project_name):
                    project_id = str(keystone.tenants.find(
                        name=project_name).id)
        else:
            raise RuntimeError('Project name or project id should'
                               ' not be empty and should be string')

        if not mistral_url:
            catalog = keystone.service_catalog.get_endpoints(service_type)
            if service_type in catalog:
                for e_type, endpoint in catalog.get[service_type][0].items():
                    if str(e_type).lower() == str(endpoint_type).lower():
                        mistral_url = endpoint
                        break

        if not mistral_url:
            mistral_url = "http://localhost:8989/v1"

        return mistral_url, token, project_id, user_id
