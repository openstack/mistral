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

from mistral.db.v2 import api as db_api
from mistral.tests.unit import base as test_base


WF_EXECS = [
    {
        'name': '1',
        'spec': {},
        'start_params': {},
        'state': 'RUNNING',
        'state_info': "Running...",
        'created_at': None,
        'updated_at': None,
        'context': None,
        'task_id': None,
        'trust_id': None
    },
    {
        'name': '1',
        'spec': {},
        'start_params': {},
        'state': 'RUNNING',
        'state_info': "Running...",
        'created_at': None,
        'updated_at': None,
        'context': None,
        'task_id': None,
        'trust_id': None
    }
]


class TransactionsTest(test_base.DbTestCase):

    def setUp(self):
        super(TransactionsTest, self).setUp()

        cfg.CONF.set_default('auth_enable', True, group='pecan')

        self.addCleanup(
            cfg.CONF.set_default,
            'auth_enable',
            False,
            group='pecan'
        )

    def test_read_only_transactions(self):
        with db_api.transaction():
            db_api.create_workflow_execution(WF_EXECS[0])

            wf_execs = db_api.get_workflow_executions()
            self.assertEqual(1, len(wf_execs))

        wf_execs = db_api.get_workflow_executions()
        self.assertEqual(1, len(wf_execs))

        with db_api.transaction(read_only=True):
            db_api.create_workflow_execution(WF_EXECS[1])

            wf_execs = db_api.get_workflow_executions()
            self.assertEqual(2, len(wf_execs))

        wf_execs = db_api.get_workflow_executions()
        self.assertEqual(1, len(wf_execs))
