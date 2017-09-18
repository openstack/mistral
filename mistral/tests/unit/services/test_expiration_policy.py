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
from mistral.services.expiration_policy import ExecutionExpirationPolicy
from mistral.tests.unit import base
from mistral.tests.unit.base import get_context
from oslo_config import cfg


def _create_workflow_executions():
    time_now = datetime.datetime.utcnow()

    wf_execs = [
        {
            'id': 'success_expired',
            'name': 'success_expired',
            'created_at': time_now - datetime.timedelta(minutes=60),
            'updated_at': time_now - datetime.timedelta(minutes=59),
            'workflow_name': 'test_exec',
            'state': "SUCCESS",
        },
        {
            'id': 'error_expired',
            'name': 'error_expired',
            'created_at': time_now - datetime.timedelta(days=3, minutes=10),
            'updated_at': time_now - datetime.timedelta(days=3),
            'workflow_name': 'test_exec',
            'state': "ERROR",
        },
        {
            'id': 'running_not_expired',
            'name': 'running_not_expired',
            'created_at': time_now - datetime.timedelta(days=3, minutes=10),
            'updated_at': time_now - datetime.timedelta(days=3),
            'workflow_name': 'test_exec',
            'state': "RUNNING",
        },
        {
            'id': 'running_not_expired2',
            'name': 'running_not_expired2',
            'created_at': time_now - datetime.timedelta(days=3, minutes=10),
            'updated_at': time_now - datetime.timedelta(days=4),
            'workflow_name': 'test_exec',
            'state': "RUNNING",
        },
        {
            'id': 'success_not_expired',
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
            'id': 'cancelled_not_expired',
            'name': 'cancelled_not_expired',
            'created_at': time_now - datetime.timedelta(minutes=15),
            'updated_at': time_now - datetime.timedelta(minutes=6),
            'workflow_name': 'test_exec',
            'state': "CANCELLED",
        }
    ]

    for wf_exec in wf_execs:
        db_api.create_workflow_execution(wf_exec)

    # Create a nested workflow execution.

    db_api.create_task_execution(
        {
            'id': 'running_not_expired',
            'workflow_execution_id': 'success_not_expired',
            'name': 'my_task'
        }
    )

    db_api.create_workflow_execution(
        {
            'id': 'expired_but_not_a_parent',
            'name': 'expired_but_not_a_parent',
            'created_at': time_now - datetime.timedelta(days=15),
            'updated_at': time_now - datetime.timedelta(days=10),
            'workflow_name': 'test_exec',
            'state': "SUCCESS",
            'task_execution_id': 'running_not_expired'
        }
    )


def _switch_context(is_default, is_admin):
    ctx.set_ctx(get_context(is_default, is_admin))


class ExpirationPolicyTest(base.DbTestCase):
    def test_expiration_policy_for_executions_with_different_project_id(self):
        # Delete execution uses a secured filtering and we need
        # to verify that admin able to do that for other projects.
        cfg.CONF.set_default('auth_enable', True, group='pecan')

        # Since we are removing other projects execution,
        # we want to load the executions with other project_id.
        _switch_context(False, False)

        _create_workflow_executions()

        now = datetime.datetime.utcnow()

        # This execution has a parent wf and testing that we are
        # querying only for parent wfs.
        exec_child = db_api.get_workflow_execution('expired_but_not_a_parent')

        self.assertEqual('running_not_expired', exec_child.task_execution_id)

        # Call for all expired wfs execs.
        execs = db_api.get_expired_executions(now)

        # Should be only 5, the RUNNING execution shouldn't return,
        # so the child wf (that has parent task id).
        self.assertEqual(5, len(execs))

        # Switch context to Admin since expiration policy running as Admin.
        _switch_context(True, True)

        _set_expiration_policy_config(evaluation_interval=1, older_than=30)
        expiration_policy.run_execution_expiration_policy(self, ctx)

        # Only non_expired available (update_at < older_than).
        execs = db_api.get_expired_executions(now)

        self.assertEqual(2, len(execs))
        self.assertListEqual(
            [
                'cancelled_not_expired',
                'success_not_expired'
            ],
            sorted([ex.id for ex in execs])
        )

        _set_expiration_policy_config(evaluation_interval=1, older_than=5)
        expiration_policy.run_execution_expiration_policy(self, ctx)
        execs = db_api.get_expired_executions(now)

        self.assertEqual(0, len(execs))

    def test_deletion_of_expired_executions_with_batch_size_scenario1(self):
        """scenario1

        This test will use batch_size of 3,
        5 expired executions and different values of "older_than"
        which is 30 and 5 minutes respectively.
        Expected_result: All expired executions are successfully deleted.
        """

        _create_workflow_executions()
        now = datetime.datetime.utcnow()

        _set_expiration_policy_config(
            evaluation_interval=1,
            older_than=30,
            batch_size=3
        )
        expiration_policy.run_execution_expiration_policy(self, ctx)
        execs = db_api.get_expired_executions(now)
        self.assertEqual(2, len(execs))

        _set_expiration_policy_config(evaluation_interval=1, older_than=5)
        expiration_policy.run_execution_expiration_policy(self, ctx)
        execs = db_api.get_expired_executions(now)
        self.assertEqual(0, len(execs))

    def test_deletion_of_expired_executions_with_batch_size_scenario2(self):
        """scenario2

        This test will use batch_size of 2, 5 expired executions
        with value of "older_than" that is 5 minutes.
        Expected_result: All expired executions are successfully deleted.
        """

        _create_workflow_executions()
        now = datetime.datetime.utcnow()

        _set_expiration_policy_config(
            evaluation_interval=1,
            older_than=5,
            batch_size=2
        )
        expiration_policy.run_execution_expiration_policy(self, ctx)
        execs = db_api.get_expired_executions(now)
        self.assertEqual(0, len(execs))

    def test_expiration_policy_for_executions_with_max_executions_scen1(self):
        """scenario1

        Tests the max_executions logic with
        max_finished_executions =
        'total not expired and completed executions' - 1
        """

        _create_workflow_executions()
        _set_expiration_policy_config(
            evaluation_interval=1,
            older_than=30,
            mfe=1
        )
        expiration_policy.run_execution_expiration_policy(self, ctx)

        # Assert the two running executions
        # (running_not_expired, running_not_expired2),
        # the sub execution (expired_but_not_a_parent) and the one allowed
        # finished execution (success_not_expired) are there.
        execs = db_api.get_workflow_executions()
        self.assertEqual(4, len(execs))
        self.assertListEqual(
            [
                'expired_but_not_a_parent',
                'running_not_expired',
                'running_not_expired2',
                'success_not_expired'
            ],
            sorted([ex.id for ex in execs])
        )

    def test_expiration_policy_for_executions_with_max_executions_scen2(self):
        """scenario2

        Tests the max_executions logic with:
        max_finished_executions > total completed executions
        """

        _create_workflow_executions()
        _set_expiration_policy_config(
            evaluation_interval=1,
            older_than=30,
            mfe=100
        )
        expiration_policy.run_execution_expiration_policy(self, ctx)

        # Assert the two running executions
        # (running_not_expired, running_not_expired2), the sub execution
        # (expired_but_not_a_parent) and the all finished execution
        # (success_not_expired, 'cancelled_not_expired') are there.
        execs = db_api.get_workflow_executions()
        self.assertEqual(5, len(execs))
        self.assertListEqual(
            [
                'cancelled_not_expired',
                'expired_but_not_a_parent',
                'running_not_expired',
                'running_not_expired2',
                'success_not_expired'
            ],
            sorted([ex.id for ex in execs])
        )

    def test_periodic_task_parameters(self):
        _set_expiration_policy_config(
            evaluation_interval=17,
            older_than=13
        )

        e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

        self.assertEqual(
            17 * 60,
            e_policy._periodic_spacing['run_execution_expiration_policy']
        )

    def test_periodic_task_scheduling(self):
        def _assert_scheduling(expiration_policy_config, should_schedule):
            ExecutionExpirationPolicy._periodic_tasks = []
            _set_expiration_policy_config(*expiration_policy_config)
            e_policy = expiration_policy.ExecutionExpirationPolicy(cfg.CONF)

            if should_schedule:
                self.assertTrue(
                    e_policy._periodic_tasks,
                    "Periodic task should have been created."
                )
            else:
                self.assertFalse(
                    e_policy._periodic_tasks,
                    "Periodic task shouldn't have been created."
                )

        _assert_scheduling([1, 1, None, None], True)
        _assert_scheduling([1, None, 1, None], True)
        _assert_scheduling([1, 1, 1, None], True)
        _assert_scheduling([1, None, None, None], False)
        _assert_scheduling([None, 1, 1, None], False)
        _assert_scheduling([None, 1, 1, None], False)
        _assert_scheduling([1, 0, 0, 0], False)
        _assert_scheduling([0, 1, 1, 0], False)
        _assert_scheduling([0, 1, 1, 0], False)

    def tearDown(self):
        """Restores the size limit config to default."""
        super(ExpirationPolicyTest, self).tearDown()

        cfg.CONF.set_default('auth_enable', False, group='pecan')

        ctx.set_ctx(None)

        _set_expiration_policy_config(None, None, None, None)


def _set_expiration_policy_config(evaluation_interval, older_than, mfe=0,
                                  batch_size=0):
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
    cfg.CONF.set_default(
        'max_finished_executions',
        mfe,
        group='execution_expiration_policy'
    )
    cfg.CONF.set_default(
        'batch_size',
        batch_size,
        group='execution_expiration_policy'
    )
