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


import eventlet
from eventlet import semaphore
from oslo_config import cfg
import testtools

from mistral.db.v2.sqlalchemy import api as db_api
from mistral.tests.unit import base as test_base


WF_EXEC = {
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


@testtools.skipIf(
    'sqlite' not in cfg.CONF.database.connection,
    'SQLite is not used for the database backend.')
class SQLiteTransactionsTest(test_base.DbTestCase):
    """The purpose of this test is to research transactions of SQLite."""

    def setUp(self):
        super(SQLiteTransactionsTest, self).setUp()

        cfg.CONF.set_default('auth_enable', True, group='pecan')

        self.addCleanup(
            cfg.CONF.set_default,
            'auth_enable',
            False,
            group='pecan'
        )

    def test_dirty_reads(self):
        sem1 = semaphore.Semaphore(0)
        sem2 = semaphore.Semaphore(0)

        def _run_tx1():
            with db_api.transaction():
                wf_ex = db_api.create_workflow_execution(WF_EXEC)

                # Release TX2 so it can read data.
                sem2.release()

                print("Created: %s" % wf_ex)
                print("Holding TX1...")

                sem1.acquire()

            print("TX1 completed.")

        def _run_tx2():
            with db_api.transaction():
                print("Holding TX2...")

                sem2.acquire()

                wf_execs = db_api.get_workflow_executions()

                print("Read: %s" % wf_execs)

                self.assertEqual(1, len(wf_execs))

                # Release TX1 so it can complete.
                sem1.release()

            print("TX2 completed.")

        t1 = eventlet.spawn(_run_tx1)
        t2 = eventlet.spawn(_run_tx2)

        t1.wait()
        t2.wait()
        t1.kill()
        t2.kill()
