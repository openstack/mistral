# -*- coding: utf-8 -*-
#
# Copyright 2013 - Alcatel-lucent, Inc.
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


import datetime
from mistral.context import ctx

from mistral.db.v2 import api as db_api
from mistral.services import expiration_policy
from mistral.tests.unit.api import base
from oslo_config import cfg

WORKFLOW_EXECS = [
    {
        'id': '123',
        'name': 'success_expired',
        'created_at': datetime.datetime.now() - datetime.timedelta(minutes=31),
        'updated_at': datetime.datetime.now() - datetime.timedelta(minutes=30),
        'workflow_name': 'test_exec',
        'state': "SUCCESS",
    },
    {
        'id': '456',
        'name': 'error_expired',
        'created_at': datetime.datetime.now() - datetime.timedelta(days=3,
                                                                   minutes=10),
        'updated_at': datetime.datetime.now() - datetime.timedelta(days=3),
        'workflow_name': 'test_exec',
        'state': "ERROR",
    },
    {
        'id': '789',
        'name': 'running_not_expired',
        'created_at': datetime.datetime.now() - datetime.timedelta(days=3,
                                                                   minutes=10),
        'updated_at': datetime.datetime.now() - datetime.timedelta(days=3),
        'workflow_name': 'test_exec',
        'state': "RUNNING",
    },
    {
        'id': '987',
        'name': 'success_not_expired',
        'created_at': datetime.datetime.now() - datetime.timedelta(minutes=15),
        'updated_at': datetime.datetime.now() - datetime.timedelta(minutes=5),
        'workflow_name': 'test_exec',
        'state': "SUCCESS",
    },
    {
        'id': '654',
        'name': 'expired but not a parent',
        'created_at': datetime.datetime.now() - datetime.timedelta(days=15),
        'updated_at': datetime.datetime.now() - datetime.timedelta(days=10),
        'workflow_name': 'test_exec',
        'state': "SUCCESS",
        'task_execution_id': '789'
    }
]


def _load_executions():

    for wf_exec in WORKFLOW_EXECS:
        db_api.create_workflow_execution(wf_exec)


class ExpirationPolicyTest(base.FunctionalTest):
    def test_expiration_policy_for_executions(self):
        _load_executions()

        now = datetime.datetime.now()

        # This execution has a parent wf and testing that we are
        # Querying only for parent wfs.
        exec_child = db_api.get_execution('654')

        self.assertEqual(exec_child.task_execution_id, '789')

        # Call for all expired wfs execs.
        execs = db_api.get_expired_executions(now)

        # Should be only 3, the RUNNING execution shouldn't return,
        # So the child wf (that has parent task id).
        self.assertEqual(len(execs), 3)

        _set_expiration_policy_config(1, 10)
        expiration_policy.run_execution_expiration_policy(self, ctx)

        # Only non_expired available (update_at < older_than).
        execs = db_api.get_expired_executions(now)

        self.assertEqual(len(execs), 1)
        self.assertEqual(execs[0].id, '987')

        _set_expiration_policy_config(1, 5)
        expiration_policy.run_execution_expiration_policy(self, ctx)
        execs = db_api.get_expired_executions(now)

        self.assertEqual(len(execs), 0)

    def test_negative_wrong_conf_values(self):
        _set_expiration_policy_config(None, None)
        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertEqual(e_policy._periodic_spacing, {})
        self.assertEqual(e_policy._periodic_tasks, [])

        _set_expiration_policy_config(None, 60)
        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertEqual(e_policy._periodic_spacing, {})
        self.assertEqual(e_policy._periodic_tasks, [])

        _set_expiration_policy_config(60, None)
        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertEqual(e_policy._periodic_spacing, {})
        self.assertEqual(e_policy._periodic_tasks, [])

    def test_periodic_task_parameters(self):
        _set_expiration_policy_config(17, 13)

        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)
        self.assertEqual(e_policy._periodic_spacing
                         ['run_execution_expiration_policy'], 17 * 60)

    def tearDown(self):
        """Restores the size limit config to default."""
        super(ExpirationPolicyTest, self).tearDown()
        _set_expiration_policy_config(None, None)


def _set_expiration_policy_config(evaluation_interval, older_than):
    cfg.CONF.set_default(
        'evaluation_interval',
        evaluation_interval,
        group='execution_expiration_policy'
    )
    cfg.CONF.set_default(
        'older_than',
        older_than,
        group='execution_expiration_policy'
    )
