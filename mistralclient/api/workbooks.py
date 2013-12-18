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

from mistralclient.api import base


class Workbook(base.Resource):
    resource_name = 'Workbook'


class WorkbookManager(base.ResourceManager):
    resource_class = Workbook

    def create(self, name, description=None, tags=None):
        self._ensure_not_empty(name=name)

        data = {
            'name': name,
            'description': description,
            'tags': tags,
        }

        return self._create('/workbooks', data)

    def update(self, name, description=None, tags=None):
        self._ensure_not_empty(name=name)

        data = {
            'name': name,
            'description': description,
            'tags': tags,
        }

        return self._update('/workbooks', data)

    def list(self):
        return self._list('/workbooks', 'workbooks')

    def get(self, name):
        self._ensure_not_empty(name=name)

        return self._get('/workbooks/%s' % name)

    def delete(self, name):
        self._ensure_not_empty(name=name)

        self._delete('/workbooks/%s' % name)

    def upload_definition(self, name, text):
        self._ensure_not_empty(name=name)

        self.client.http_client.put('/workbooks/%s/definition' % name,
                                    text,
                                    headers={'content-type': 'text/plain'})

    def get_definition(self, name):
        self._ensure_not_empty(name=name)

        return self.client.http_client.get('/workbooks/%s/definition'
                                           % name).content
