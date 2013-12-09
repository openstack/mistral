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


class Listener(base.Resource):
    resource_name = 'Listener'


class ListenerManager(base.ResourceManager):
    resource_class = Listener

    def create(self, workbook_name, webhook, description=None, events=None):
        # TODO(rakhmerov): need to describe what events is (data type)

        self._ensure_not_empty(workbook_name=workbook_name,
                               webhook=webhook)
        data = {
            'workbook_name': workbook_name,
            'description': description,
            'webhook': webhook,
            'events': events
        }

        return self._create('/workbooks/%s/listeners' % workbook_name, data)

    def update(self, workbook_name, id, webhook=None, description=None,
               events=None):
        #TODO: need to describe what events is
        self._ensure_not_empty(workbook_name=workbook_name, id=id)

        data = {
            'id': id,
            'workbook_name': workbook_name,
            'description': description,
            'webhook': webhook,
            'events': events
        }

        return self._update('/workbooks/%s/listeners/%s' %
                            (workbook_name, id), data)

    def list(self, workbook_name):
        self._ensure_not_empty(workbook_name=workbook_name)

        return self._list('/workbooks/%s/listeners' % workbook_name,
                          'listeners')

    def get(self, workbook_name, id):
        self._ensure_not_empty(workbook_name=workbook_name, id=id)

        return self._get('/workbooks/%s/listeners/%s' % (workbook_name, id))

    def delete(self, workbook_name, id):
        self._ensure_not_empty(workbook_name=workbook_name, id=id)

        self._delete('/workbooks/%s/listeners/%s' % (workbook_name, id))
