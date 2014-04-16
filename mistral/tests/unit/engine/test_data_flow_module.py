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

from mistral.engine import data_flow
from mistral.tests import base
from mistral.db import api as db_api

from mistral.openstack.common import log as logging

LOG = logging.getLogger(__name__)

WB_NAME = 'my_workbook'
EXEC_ID = '1'

CONTEXT = {
    'param1': 'val1',
    'param2': 'val2',
    'param3': {
        'param31': 'val31',
        'param32': 'val32'
    }
}

TASK = {
    'workbook_name': WB_NAME,
    'execution_id': EXEC_ID,
    'name': 'my_task',
    'task_spec': {
        'parameters': {
            'p1': 'My string',
            'p2': '$.param3.param32',
            'p3': ''
        },
        'publish': {
            'new_key11': 'new_key1'
        }
    },
    'service_spec': {
        'actions': {
            'action': {
                'output': {
                    # This one should not be evaluated.
                    'server_id': '$.server.id'
                }
            }
        }
    },
    'in_context': CONTEXT
}


class DataFlowModuleTest(base.DbTestCase):
    def test_evaluate_task_parameters(self):
        parameters = data_flow.evaluate_task_parameters(TASK, CONTEXT)

        self.assertEqual(3, len(parameters))
        self.assertEqual('My string', parameters['p1'])
        self.assertEqual('val32', parameters['p2'])

    def test_prepare_tasks(self):
        task = db_api.task_create(WB_NAME, EXEC_ID, TASK.copy())
        tasks = [task]

        data_flow.prepare_tasks(tasks, CONTEXT)

        db_task = db_api.task_get(WB_NAME, EXEC_ID, tasks[0]['id'])

        self.assertDictEqual(CONTEXT, db_task['in_context'])
        self.assertDictEqual({'p1': 'My string',
                              'p2': 'val32',
                              'p3': ''},
                             db_task['parameters'])

    def test_get_outbound_context(self):
        output = data_flow.get_task_output(TASK, {'new_key1': 'new_val1'})

        self.assertDictEqual(
            {
                'new_key11': 'new_val1',
                'task': {
                    'my_task': {
                        'new_key1': 'new_val1'
                    }
                }
            },
            output)
