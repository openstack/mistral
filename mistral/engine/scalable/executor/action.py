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


class BaseAction(object):
    def do_action(self):
        pass


class RESTAction(BaseAction):
    def __init__(self, url, params={}, method="GET", headers=None):
        self.url = url
        self.params = params
        self.method = method
        self.headers = headers

    def do_action(self):
        requests.request(self.method, self.url, params=self.params,
                         headers=self.headers)

# TODO(rakhmerov): add other types of actions.
