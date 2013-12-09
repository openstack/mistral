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


class HTTPClient(object):
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token

    def get(self, url, headers=None):
        if not headers:
            headers = {}

        headers['x-auth-token'] = self.token

        return requests.get(self.base_url + url, headers=headers)

    def post(self, url, body, headers=None):
        if not headers:
            headers = {'content-type': 'application/json'}

        headers['x-auth-token'] = self.token

        return requests.post(self.base_url + url, body, headers=headers)

    def put(self, url, body, headers=None):
        if not headers:
            headers = {'content-type': 'application/json'}

        headers['x-auth-token'] = self.token

        return requests.put(self.base_url + url, body, headers=headers)

    def delete(self, url, headers=None):
        if not headers:
            headers = {}

        headers['x-auth-token'] = self.token

        return requests.delete(self.base_url + url, headers=headers)
