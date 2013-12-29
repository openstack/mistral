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

import logging
from pecan import abort
from pecan import rest
import pecan
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from demo_app import tasks


LOG = logging.getLogger(__name__)


class Controller(rest.RestController):
    """API root controller"""

    @wsme_pecan.wsexpose(wtypes.text)
    def get_all(self):
        LOG.debug("Fetch items.")

        values = {
            'tasks': [
                'task1',
                'task2',
                'task3',
                'task4'
            ]
        }

        if not values:
            abort(404)
        else:
            return values

    @wsme_pecan.wsexpose(wtypes.text, wtypes.text)
    def get(self, name):
        print("Task '%s' is starting" % name)

        value = "Task %s accepted" % name
        tasks.start_task(**self.get_mistral_headers())
        return value

    def get_mistral_headers(self):
        headers = pecan.request.headers
        try:
            needed_headers = {
                'workbook_name': headers['Mistral-Workbook-Name'],
                'execution_id': headers['Mistral-Execution-Id'],
                'task_id': headers['Mistral-Task-Id']
            }
            return needed_headers
        except KeyError:
            raise RuntimeError("Could not find http headers for "
                               "defining mistral task")
