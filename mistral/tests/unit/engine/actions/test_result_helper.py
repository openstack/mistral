# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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

import mock
import requests

from mistral.engine.actions import action_types
from mistral.engine.actions import action_factory
from mistral.tests import base


SAMPLE_TASK = {
    'task_spec': {
        'action': 'MyRest:create-vm',
        'parameters': {
            'a': 'b'
        },
        'headers': {
            'Cookie': 'abc'
        },
        'name': 'create-vms'
    },
    'service_spec': {
        'parameters': {
            'baseUrl': 'http://some_host'
        },
        'actions': {
            'create-vm': {
                'parameters': {
                    'url': '/task1'
                }
            }
        },
        'name': 'MyRest'
    },
    'workbook_name': 'wb',
    'execution_id': '1234',
    'id': '123'
}

SAMPLE_RESULT_HELPER = {
    'output': {
        'vm_id': '$.server.id'
    }
}

SAMPLE_RESULT = {
    'server': {
        'id': 'afd1254-1ad3fb0'
    }
}


class FakeResponse(object):
    def __init__(self):
        self.status_code = 200
        self.content = SAMPLE_RESULT

    def json(self):
        return self.content


class ResultHelperTest(base.BaseTest):
    @mock.patch.object(requests, "request",
                       mock.MagicMock(return_value=FakeResponse()))
    def test_action_result_with_results(self):
        task = copy.deepcopy(SAMPLE_TASK)
        task['service_spec'].update({'type': action_types.REST_API})
        create_vm = task['service_spec']['actions']['create-vm']
        create_vm.update(SAMPLE_RESULT_HELPER)
        action = action_factory.create_action(task)
        result = action.run()
        self.assertEqual(result, {'vm_id': SAMPLE_RESULT['server']['id']})

    @mock.patch.object(requests, "request",
                       mock.MagicMock(return_value=FakeResponse()))
    def test_action_result_without_results(self):
        task = copy.deepcopy(SAMPLE_TASK)
        task['service_spec'].update({'type': action_types.REST_API})
        action = action_factory.create_action(task)
        result = action.run()
        self.assertEqual(result, SAMPLE_RESULT)
