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


class Task(base.Resource):
    resource_name = 'Task'


class TaskManager(base.ResourceManager):
    resource_class = Task

    def update(self, workbook_name, execution_id, id, state):
        self._ensure_not_empty(workbook_name=workbook_name,
                               execution_id=execution_id,
                               id=id,
                               state=state)

        data = {
            'workbook_name': workbook_name,
            'execution_id': execution_id,
            'id': id,
            'state': state
        }

        return self._update('/workbooks/%s/executions/%s/tasks/%s' %
                            (workbook_name, execution_id, id), data)

    def list(self, workbook_name, execution_id):
        self._ensure_not_empty(workbook_name=workbook_name,
                               execution_id=execution_id)

        return self._list('/workbooks/%s/executions/%s/tasks' %
                          (workbook_name, execution_id),
                          'tasks')

    def get(self, workbook_name, execution_id, id):
        self._ensure_not_empty(workbook_name=workbook_name,
                               execution_id=execution_id,
                               id=id)

        return self._get('/workbooks/%s/executions/%s/tasks/%s' %
                         (workbook_name, execution_id, id))
