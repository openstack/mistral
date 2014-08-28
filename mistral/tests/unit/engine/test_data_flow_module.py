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

import copy

from mistral.db.v1 import api as db_api
from mistral.db.v1.sqlalchemy import models
from mistral.engine import data_flow
from mistral.engine import states
from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.workbook import parser as spec_parser

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
        'action': 'std.echo',
        'parameters': {
            'p1': 'My string',
            'p2': '$.param3.param32',
            'p3': ''
        },
        'publish': {
            'new_key11': '$.new_key1'
        }
    },
    'in_context': CONTEXT
}

TASK2 = copy.deepcopy(TASK)
TASK2['task_spec']['action'] = 'some.thing'

WORKBOOK = {
    'Namespaces': {
        'some': {
            'actions': {
                'thing': {
                    'class': 'std.echo',
                    'base-parameters': {
                        'output': '{$.p1} {$.p2}'
                    }
                }
            }
        }
    },
    'Workflow': {
        'tasks': {
            'first_task': TASK['task_spec'],
            'second_task': TASK2['task_spec']
        }
    }
}


class DataFlowModuleTest(base.DbTestCase):
    def test_evaluate_task_parameters(self):
        db_task = models.Task()
        db_task.update(TASK)

        parameters = data_flow.evaluate_task_parameters(db_task, CONTEXT)

        self.assertEqual(3, len(parameters))
        self.assertEqual('My string', parameters['p1'])
        self.assertEqual('val32', parameters['p2'])

    def test_prepare_tasks(self):
        wb = spec_parser.get_workbook_spec(WORKBOOK)

        tasks = [
            db_api.task_create(EXEC_ID, TASK.copy()),
            db_api.task_create(EXEC_ID, TASK2.copy())
        ]

        executables = data_flow.prepare_tasks(tasks, CONTEXT, wb, tasks)

        self.assertEqual(2, len(executables))

        self.assertEqual(tasks[0]['id'], executables[0][0])
        self.assertEqual('std.echo', executables[0][1])
        self.assertDictEqual({'p2': 'val32', 'p3': '', 'p1': 'My string'},
                             executables[0][2])

        self.assertEqual(tasks[1]['id'], executables[1][0])
        self.assertEqual('std.echo', executables[1][1])
        self.assertDictEqual({'output': 'My string val32'},
                             executables[1][2])

        for task in tasks:
            db_task = db_api.task_get(task['id'])

            self.assertDictEqual(CONTEXT, db_task['in_context'])
            self.assertDictEqual({'p1': 'My string',
                                  'p2': 'val32',
                                  'p3': ''},
                                 db_task['parameters'])
            self.assertEqual(states.RUNNING, db_task['state'])

    def test_get_outbound_context(self):
        db_task = models.Task()
        db_task.update(TASK)

        output = data_flow.get_task_output(db_task, {'new_key1': 'new_val1'})

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
