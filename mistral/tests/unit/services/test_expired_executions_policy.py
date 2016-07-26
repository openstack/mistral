# Copyright 2015 - Alcatel-lucent, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from mistral import context as ctx
from mistral.db.v2 import api as db_api
from mistral.services import expiration_policy
from mistral.tests.unit import base
from oslo_config import cfg


def _create_workflow_executions():
    time_now = datetime.datetime.now()

    wf_execs = [
        {
            'id': '123',
            'name': 'success_expired',
            'created_at': time_now - datetime.timedelta(minutes=60),
            'updated_at': time_now - datetime.timedelta(minutes=59),
            'workflow_name': 'test_exec',
            'state': "SUCCESS",
        },
        {
            'id': '456',
            'name': 'error_expired',
            'created_at': time_now - datetime.timedelta(days=3, minutes=10),
            'updated_at': time_now - datetime.timedelta(days=3),
            'workflow_name': 'test_exec',
            'state': "ERROR",
        },
        {
            'id': '789',
            'name': 'running_not_expired',
            'created_at': time_now - datetime.timedelta(days=3, minutes=10),
            'updated_at': time_now - datetime.timedelta(days=3),
            'workflow_name': 'test_exec',
            'state': "RUNNING",
        },
        {
            'id': '987',
            'name': 'success_not_expired',
            'created_at': time_now - datetime.timedelta(minutes=15),
            'updated_at': time_now - datetime.timedelta(minutes=5),
            'workflow_name': 'test_exec',
            'state': "SUCCESS",
        },
        {
            'id': 'abc',
            'name': 'cancelled_expired',
            'created_at': time_now - datetime.timedelta(minutes=60),
            'updated_at': time_now - datetime.timedelta(minutes=59),
            'workflow_name': 'test_exec',
            'state': "CANCELLED",
        },
        {
            'id': 'def',
            'name': 'cancelled_not_expired',
            'created_at': time_now - datetime.timedelta(minutes=15),
            'updated_at': time_now - datetime.timedelta(minutes=5),
            'workflow_name': 'test_exec',
            'state': "CANCELLED",
        }
    ]

    for wf_exec in wf_execs:
        db_api.create_workflow_execution(wf_exec)

    # Create a nested workflow execution.

    db_api.create_task_execution(
        {
            'id': '789',
            'workflow_execution_id': '987',
            'name': 'my_task'
        }
    )

    db_api.create_workflow_execution(
        {
            'id': '654',
            'name': 'expired but not a parent',
            'created_at': time_now - datetime.timedelta(days=15),
            'updated_at': time_now - datetime.timedelta(days=10),
            'workflow_name': 'test_exec',
            'state': "SUCCESS",
            'task_execution_id': '789'
        }
    )


def _switch_context(project_id, is_admin):
    _ctx = ctx.MistralContext(
        user_id=None,
        project_id=project_id,
        auth_token=None,
        is_admin=is_admin
    )

    ctx.set_ctx(_ctx)


class ExpirationPolicyTest(base.DbTestCase):
    def test_expiration_policy_for_executions(self):
        # Delete execution uses a secured filtering and we need
        # to verify that admin able to do that for other projects.
        cfg.CONF.set_default('auth_enable', True, group='pecan')

        # Since we are removing other projects execution,
        # we want to load the executions with other project_id.
        _switch_context('non_admin_project', False)

        _create_workflow_executions()

        now = datetime.datetime.now()

        # This execution has a parent wf and testing that we are
        # querying only for parent wfs.
        exec_child = db_api.get_workflow_execution('654')

        self.assertEqual('789', exec_child.task_execution_id)

        # Call for all expired wfs execs.
        execs = db_api.get_expired_executions(now)

        # Should be only 5, the RUNNING execution shouldn't return,
        # so the child wf (that has parent task id).
        self.assertEqual(5, len(execs))

        # Switch context to Admin since expiration policy running as Admin.
        _switch_context(None, True)

        _set_expiration_policy_config(1, 30)
        expiration_policy.run_execution_expiration_policy(self, ctx)

        # Only non_expired available (update_at < older_than).
        execs = db_api.get_expired_executions(now)

        self.assertEqual(2, len(execs))
        self.assertListEqual(['987', 'def'], sorted([ex.id for ex in execs]))

        _set_expiration_policy_config(1, 5)
        expiration_policy.run_execution_expiration_policy(self, ctx)
        execs = db_api.get_expired_executions(now)

        self.assertEqual(0, len(execs))

    def test_negative_wrong_conf_values(self):
        _set_expiration_policy_config(None, None)
        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertDictEqual({}, e_policy._periodic_spacing)
        self.assertListEqual([], e_policy._periodic_tasks)

        _set_expiration_policy_config(None, 60)
        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertDictEqual({}, e_policy._periodic_spacing)
        self.assertListEqual([], e_policy._periodic_tasks)

        _set_expiration_policy_config(60, None)
        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertDictEqual({}, e_policy._periodic_spacing)
        self.assertListEqual([], e_policy._periodic_tasks)

    def test_periodic_task_parameters(self):
        _set_expiration_policy_config(17, 13)

        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertEqual(17 * 60, e_policy._periodic_spacing
                         ['run_execution_expiration_policy'])

    def tearDown(self):
        """Restores the size limit config to default."""
        super(ExpirationPolicyTest, self).tearDown()

        cfg.CONF.set_default('auth_enable', False, group='pecan')

        ctx.set_ctx(None)

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
