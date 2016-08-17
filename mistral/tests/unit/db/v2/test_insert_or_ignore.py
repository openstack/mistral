# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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


from oslo_config import cfg

from mistral.db.v2.sqlalchemy import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.tests.unit import base as test_base

WF_EX = {
    'id': '1',
    'spec': {},
    'start_params': {'task': 'my_task1'},
    'state': 'IDLE',
    'state_info': "Running...",
    'created_at': None,
    'updated_at': None,
    'context': None,
    'task_id': None,
    'trust_id': None,
    'description': None,
    'output': None
}


TASK_EX = {
    'workflow_execution_id': '1',
    'workflow_name': 'my_wf',
    'name': 'my_task1',
    'spec': None,
    'action_spec': None,
    'state': 'IDLE',
    'tags': ['deployment'],
    'in_context': None,
    'runtime_context': None,
    'created_at': None,
    'updated_at': None
}


class InsertOrIgnoreTest(test_base.DbTestCase):
    def setUp(self):
        super(InsertOrIgnoreTest, self).setUp()

        cfg.CONF.set_default('auth_enable', True, group='pecan')

        db_api.create_workflow_execution(WF_EX)

        self.addCleanup(
            cfg.CONF.set_default,
            'auth_enable',
            False,
            group='pecan'
        )

    def test_insert_or_ignore_without_conflicts(self):
        db_api.insert_or_ignore(
            db_models.TaskExecution,
            TASK_EX.copy()
        )

        task_execs = db_api.get_task_executions()

        self.assertEqual(1, len(task_execs))

        task_ex = task_execs[0]

        self._assert_dict_contains_subset(TASK_EX, task_ex.to_dict())

    def test_insert_or_ignore_with_conflicts(self):
        # Insert the first object.
        values = TASK_EX.copy()

        values['unique_key'] = 'key'

        db_api.insert_or_ignore(db_models.TaskExecution, values)

        task_execs = db_api.get_task_executions()

        self.assertEqual(1, len(task_execs))

        task_ex = task_execs[0]

        self._assert_dict_contains_subset(TASK_EX, task_ex.to_dict())

        # Insert the second object with the same unique key.
        # We must not get exceptions and new object must not be saved.
        values = TASK_EX.copy()

        values['unique_key'] = 'key'

        db_api.insert_or_ignore(db_models.TaskExecution, values)

        task_execs = db_api.get_task_executions()

        self.assertEqual(1, len(task_execs))

        task_ex = task_execs[0]

        self._assert_dict_contains_subset(TASK_EX, task_ex.to_dict())
