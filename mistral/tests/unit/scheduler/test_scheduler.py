# Copyright 2018 - Nokia Networks.
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

from eventlet import event
from eventlet import semaphore
from eventlet import timeout

import datetime
import mock

from mistral.db.v2 import api as db_api
from mistral.scheduler import base as scheduler_base
from mistral.scheduler import default_scheduler
from mistral.tests.unit import base


TARGET_METHOD_PATH = (
    'mistral.tests.unit.scheduler.test_scheduler.target_method'
)


def target_method():
    pass


class SchedulerTest(base.DbTestCase):
    def setUp(self):
        super(SchedulerTest, self).setUp()

        # This Timeout object is needed to raise an exception if the test took
        # longer than a configured number of seconds.
        self.timeout = timeout.Timeout(seconds=15)

        # Synchronization primitives to control when a scheduled invoked
        # method is allowed to enter the method and exit from it to perform
        # all needed checks.
        self.target_mtd_started = event.Event()
        self.target_mtd_finished = event.Event()
        self.target_mtd_lock = semaphore.Semaphore(0)

        self.scheduler = default_scheduler.DefaultScheduler(1, 1, 100)
        self.scheduler.start()

        self.addCleanup(self.scheduler.stop, True)
        self.addCleanup(self.timeout.cancel)

    def target_method(self, *args, **kwargs):
        self.target_mtd_started.send()

        self.target_mtd_lock.acquire()

        # Note: Potentially we can do something else here. No-op for now.

        self.target_mtd_finished.send()

    def _wait_target_method_start(self):
        self.target_mtd_started.wait()

    def _unlock_target_method(self):
        self.target_mtd_lock.release()

    def _wait_target_method_end(self):
        self.target_mtd_finished.wait()

    @mock.patch(TARGET_METHOD_PATH)
    def test_schedule_called_once(self, method):
        method.side_effect = self.target_method

        job = scheduler_base.SchedulerJob(
            run_after=1,
            func_name=TARGET_METHOD_PATH,
            func_args={'name': 'task', 'id': '321'}
        )

        self.scheduler.schedule(job)

        self._wait_target_method_start()

        # Check that the persistent job has been created and captured.
        scheduled_jobs = db_api.get_scheduled_jobs()

        self.assertEqual(1, len(scheduled_jobs))

        captured_at = scheduled_jobs[0].captured_at

        self.assertIsNotNone(captured_at)
        self.assertTrue(
            datetime.datetime.utcnow() - captured_at <
            datetime.timedelta(seconds=3)
        )

        self._unlock_target_method()
        self._wait_target_method_end()

        method.assert_called_once_with(name='task', id='321')

        # After the job is processed the persistent object must be deleted.
        self._await(lambda: not db_api.get_scheduled_jobs())

    @mock.patch(TARGET_METHOD_PATH)
    def test_pickup_from_job_store(self, method):
        method.side_effect = self.target_method

        self.override_config('pickup_job_after', 1, 'scheduler')

        # 1. Create a scheduled job in Job Store.
        execute_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=1)

        db_api.create_scheduled_job({
            'run_after': 1,
            'func_name': TARGET_METHOD_PATH,
            'func_args': {'name': 'task', 'id': '321'},
            'execute_at': execute_at,
            'captured_at': None,
            'auth_ctx': {}
        })

        self.assertTrue(len(db_api.get_scheduled_jobs()) > 0)

        self._unlock_target_method()
        self._wait_target_method_end()

        # 2. Wait till Scheduler picks up the job and processes it.
        self._await(lambda: not db_api.get_scheduled_jobs())

        method.assert_called_once_with(name='task', id='321')

    @mock.patch(TARGET_METHOD_PATH)
    def test_recapture_job(self, method):
        method.side_effect = self.target_method

        self.override_config('pickup_job_after', 1, 'scheduler')
        self.override_config('captured_job_timeout', 3, 'scheduler')

        # 1. Create a scheduled job in Job Store marked as captured in one
        #    second in the future. It can be captured again only after 3
        #    seconds after that according to the config option.
        captured_at = datetime.datetime.utcnow() + datetime.timedelta(
            seconds=1
        )

        before_ts = datetime.datetime.utcnow()

        db_api.create_scheduled_job({
            'run_after': 1,
            'func_name': TARGET_METHOD_PATH,
            'func_args': {'name': 'task', 'id': '321'},
            'execute_at': datetime.datetime.utcnow(),
            'captured_at': captured_at,
            'auth_ctx': {}
        })

        self.assertTrue(len(db_api.get_scheduled_jobs()) > 0)

        self._unlock_target_method()
        self._wait_target_method_end()

        # 2. Wait till Scheduler picks up the job and processes it.
        self._await(lambda: not db_api.get_scheduled_jobs())

        method.assert_called_once_with(name='task', id='321')

        # At least 3 seconds should have passed.
        self.assertTrue(
            datetime.datetime.utcnow() - before_ts >=
            datetime.timedelta(seconds=3)
        )
