# Copyright 2017 - Nokia Networks.
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
import datetime

from mistral.db.v2.sqlalchemy import api as db_api
from mistral.tests.unit import base as test_base
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


class DBModelTest(test_base.DbTestCase):
    def test_iterate_column_names(self):
        wf_ex = db_api.create_workflow_execution(WF_EXEC)

        self.assertIsNotNone(wf_ex)

        c_names = [c_name for c_name in wf_ex.iter_column_names()]

        expected = set(WF_EXEC.keys())

        expected.remove('some_invalid_field')

        self.assertEqual(expected, set(c_names))

    def test_iterate_columns(self):
        wf_ex = db_api.create_workflow_execution(WF_EXEC)

        self.assertIsNotNone(wf_ex)

        values = {c_name: c_val for c_name, c_val in wf_ex.iter_columns()}

        expected = copy.copy(WF_EXEC)

        del expected['some_invalid_field']

        self.assertDictEqual(expected, values)

    def test_to_dict(self):
        wf_ex = db_api.create_workflow_execution(WF_EXEC)

        self.assertIsNotNone(wf_ex)

        expected = copy.copy(WF_EXEC)

        del expected['some_invalid_field']

        actual = wf_ex.to_dict()

        # The method to_dict() returns date as strings. So, we have to
        # check them separately.

        self.assertEqual(
            utils.datetime_to_str(expected['created_at']),
            actual['created_at']
        )

        # Now check the rest of the columns.
        del expected['created_at']
        del actual['created_at']

        self.assertDictEqual(expected, actual)
