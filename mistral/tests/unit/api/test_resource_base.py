# Copyright 2016 NEC Corporation. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy
import datetime

from mistral.api.controllers.v2 import resources
from mistral.db.v2 import api as db_api
from mistral.tests.unit import base
from mistral import utils


WF_EXEC = {
    'id': 'c0f3be41-88b9-4c86-a669-83e77cd0a1b8',
    'spec': {},
    'params': {'task': 'my_task1'},
    'project_id': '<default-project>',
    'scope': 'PUBLIC',
    'state': 'IDLE',
    'state_info': "Running...",
    'created_at': datetime.datetime(2016, 12, 1, 15, 0, 0),
    'updated_at': None,
    'context': None,
    'task_execution_id': None,
    'description': None,
    'output': None,
    'accepted': False,
    'some_invalid_field': "foobar"
}


class TestRestResource(base.DbTestCase):
    def test_from_db_model(self):
        wf_ex = db_api.create_workflow_execution(WF_EXEC)

        self.assertIsNotNone(wf_ex)

        wf_ex_resource = resources.Execution.from_db_model(wf_ex)

        self.assertIsNotNone(wf_ex_resource)

        expected = copy.copy(WF_EXEC)

        del expected['some_invalid_field']
        utils.datetime_to_str_in_dict(expected, 'created_at')

        self.assertDictEqual(expected, wf_ex.to_dict())

    def test_from_dict(self):
        wf_ex = db_api.create_workflow_execution(WF_EXEC)

        self.assertIsNotNone(wf_ex)

        wf_ex_resource = resources.Execution.from_dict(wf_ex.to_dict())

        self.assertIsNotNone(wf_ex_resource)

        expected = copy.copy(WF_EXEC)

        del expected['some_invalid_field']
        utils.datetime_to_str_in_dict(expected, 'created_at')

        self.assertDictEqual(expected, wf_ex.to_dict())
