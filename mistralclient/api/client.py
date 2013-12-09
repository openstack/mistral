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

from mistralclient.api import httpclient
from mistralclient.api import workbooks
from mistralclient.api import executions
from mistralclient.api import tasks
from mistralclient.api import listeners


class Client(object):
    def __init__(self, mistral_url=None):
        # TODO: add all required parameters for Keystone authentication

        if mistral_url and not isinstance(mistral_url, six.string_types):
            raise RuntimeError('Mistral url should be a string.')

        if not mistral_url:
            mistral_url = "http://localhost:8989/v1"

        # TODO: add Keystone authentication later
        token = "TBD"

        self.http_client = httpclient.HTTPClient(mistral_url, token)

        # Create all resource managers.
        self.workbooks = workbooks.WorkbookManager(self)
        self.executions = executions.ExecutionManager(self)
        self.tasks = tasks.TaskManager(self)
        self.listeners = listeners.ListenerManager(self)
