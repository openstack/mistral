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
from oslo_config import cfg
import random
import testtools

from mistral.db.sqlalchemy import sqlite_lock
from mistral.db.v2.sqlalchemy import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
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
    'Not using SQLite for DB backend.')
class SQLiteLocksTest(test_base.DbTestCase):
    def setUp(self):
        super(SQLiteLocksTest, self).setUp()

        cfg.CONF.set_default('auth_enable', True, group='pecan')

        self.addCleanup(
            cfg.CONF.set_default,
            'auth_enable',
            False,
            group='pecan'
        )

    def _random_sleep(self):
        eventlet.sleep(random.Random().randint(0, 10) * 0.001)

    def _run_acquire_release_sqlite_lock(self, obj_id, session):
        self._random_sleep()

        sqlite_lock.acquire_lock(obj_id, session)

        self._random_sleep()

        sqlite_lock.release_locks(session)

    def test_acquire_release_sqlite_lock(self):
        threads = []

        id = "object_id"

        number = 500

        for i in range(1, number):
            threads.append(
                eventlet.spawn(self._run_acquire_release_sqlite_lock, id, i)
            )

        [t.wait() for t in threads]
        [t.kill() for t in threads]

        self.assertEqual(1, len(sqlite_lock.get_locks()))

        sqlite_lock.cleanup()

        self.assertEqual(0, len(sqlite_lock.get_locks()))

    def _run_correct_locking(self, wf_ex):
        self._random_sleep()

        with db_api.transaction():
            # Lock workflow execution and get the most up-to-date object.
            wf_ex = db_api.acquire_lock(db_models.WorkflowExecution, wf_ex.id)

            # Refresh the object.
            db_api.get_workflow_execution(wf_ex.id)

            wf_ex.name = str(int(wf_ex.name) + 1)

            return wf_ex.name

    def test_correct_locking(self):
        wf_ex = db_api.create_workflow_execution(WF_EXEC)

        threads = []

        number = 500

        for i in range(1, number):
            threads.append(
                eventlet.spawn(self._run_correct_locking, wf_ex)
            )

        [t.wait() for t in threads]
        [t.kill() for t in threads]

        wf_ex = db_api.get_workflow_execution(wf_ex.id)

        print("Correct locking test gave object name: %s" % wf_ex.name)

        self.assertEqual(str(number), wf_ex.name)
