# Copyright 2014 - Mirantis, Inc.
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

import datetime
import queue
import time
from unittest import mock

from oslo_config import cfg
from oslo_utils import timeutils

from mistral import context as auth_context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.scheduler import base as sched_base
from mistral.services import legacy_scheduler
from mistral.tests.unit import base
from mistral.tests.unit.utils.test_utils import TimeoutThreadWithException
from mistral_lib import actions as ml_actions


CONF = cfg.CONF

TARGET_METHOD_PATH = (
    'mistral.tests.unit.services.test_legacy_scheduler.target_method'
)
DELAY = 1.5


def get_time_delay(delay=DELAY * 2):
    return timeutils.utcnow() + datetime.timedelta(seconds=delay)


def target_method(*args, **kwargs):
    pass


class LegacySchedulerTest(base.DbTestCase):
    def setUp(self):
        super(LegacySchedulerTest, self).setUp()

        self.timeout_thread = TimeoutThreadWithException(10)
        self.timeout_thread.start()

        self.queue = queue.Queue()

        self.override_config('fixed_delay', 1, 'scheduler')
        self.override_config('random_delay', 0, 'scheduler')
        self.override_config('batch_size', 100, 'scheduler')

        self.scheduler = legacy_scheduler.LegacyScheduler(CONF.scheduler)
        self.scheduler.start()

        self.addCleanup(self.scheduler.stop, True)
        self.addCleanup(self.timeout_thread.stop)

        def reraise_timeout(t):
            """Re-raise a thread timeout if occured"""
            if t.exception:
                raise t.exception
        self.addCleanup(reraise_timeout, self.timeout_thread)

    def target_method(self, *args, **kwargs):
        self.queue.put(item="item")

    def target_check_context_method(self, expected_project_id):
        actual_project_id = auth_context.ctx().project_id

        self.queue.put(item=(expected_project_id == actual_project_id))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_with_factory(self, factory):
        target_method_name = 'run_something'

        factory.return_value = type(
            'something',
            (object,),
            {
                target_method_name:
                    mock.MagicMock(side_effect=self.target_method)
            }
        )

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            target_factory_func_name=TARGET_METHOD_PATH,
            func_name=target_method_name,
            func_args={'name': 'task', 'id': '123'},
            key='my_job_key'
        )

        self.scheduler.schedule(job)

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        call = self._assert_single_item(
            calls,
            target_method_name=target_method_name,
            key='my_job_key'
        )
        self.assertIn('name', call['method_arguments'])

        self.queue.get()

        factory().run_something.assert_called_once_with(name='task', id='123')

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_without_factory(self, method):
        method.side_effect = self.target_method

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            func_name=TARGET_METHOD_PATH,
            func_args={'name': 'task', 'id': '321'},
            key='my_job_key'
        )

        self.scheduler.schedule(job)

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        call = self._assert_single_item(
            calls,
            target_method_name=TARGET_METHOD_PATH,
            key='my_job_key'
        )
        self.assertIn('name', call['method_arguments'])

        self.queue.get()

        method.assert_called_once_with(name='task', id='321')

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_call_target_method_with_correct_auth(self, method):
        method.side_effect = self.target_check_context_method

        default_context = base.get_context(default=True)
        auth_context.set_ctx(default_context)

        default_project_id = default_context.project_id

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            func_name=TARGET_METHOD_PATH,
            func_args={'expected_project_id': default_project_id}
        )

        self.scheduler.schedule(job)

        second_context = base.get_context(default=False)
        auth_context.set_ctx(second_context)

        second_project_id = second_context.project_id

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            func_name=TARGET_METHOD_PATH,
            func_args={'expected_project_id': second_project_id}
        )

        self.scheduler.schedule(job)

        self.assertNotEqual(default_project_id, second_project_id)

        for _ in range(2):
            self.assertTrue(self.queue.get())

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_with_serializer(self, factory):
        target_method_name = 'run_something'

        factory.return_value = type(
            'something',
            (object,),
            {
                target_method_name:
                    mock.MagicMock(side_effect=self.target_method)
            }
        )

        task_result = ml_actions.Result('data', 'error')

        method_args = {
            'name': 'task',
            'id': '123',
            'result': task_result
        }

        serializers = {
            'result': 'mistral.workflow.utils.ResultSerializer'
        }

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            target_factory_func_name=TARGET_METHOD_PATH,
            func_name=target_method_name,
            func_args=method_args,
            func_arg_serializers=serializers
        )

        self.scheduler.schedule(job)

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        call = self._assert_single_item(
            calls,
            target_method_name=target_method_name
        )
        self.assertIn('name', call['method_arguments'])

        self.queue.get()

        result = factory().run_something.call_args[1].get('result')

        self.assertIsInstance(result, ml_actions.Result)
        self.assertEqual('data', result.data)
        self.assertEqual('error', result.error)

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_multi_instance(self, method):
        method.side_effect = self.target_method

        second_scheduler = legacy_scheduler.LegacyScheduler(CONF.scheduler)
        second_scheduler.start()

        self.addCleanup(second_scheduler.stop, True)

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            func_name=TARGET_METHOD_PATH,
            func_args={'name': 'task', 'id': '321'},
        )

        second_scheduler.schedule(job)

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        self._assert_single_item(calls, target_method_name=TARGET_METHOD_PATH)

        self.queue.get()

        method.assert_called_once_with(name='task', id='321')

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_delete_calls(self, method):
        method.side_effect = self.target_method

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            func_name=TARGET_METHOD_PATH,
            func_args={'name': 'task', 'id': '321'},
        )

        self.scheduler.schedule(job)

        calls = db_api.get_delayed_calls_to_start(get_time_delay())
        self._assert_single_item(calls, target_method_name=TARGET_METHOD_PATH)

        self.queue.get()

        time.sleep(0.1)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_delayed_call,
            calls[0].id
        )

    @mock.patch(TARGET_METHOD_PATH)
    def test_processing_true_does_not_return_in_get_delayed_calls_to_start(
            self,
            method):
        method.side_effect = self.target_method

        values = {
            'factory_method_path': None,
            'target_method_name': TARGET_METHOD_PATH,
            'execution_time': get_time_delay(),
            'auth_context': None,
            'serializers': None,
            'method_arguments': None,
            'processing': True
        }

        call = db_api.create_delayed_call(values)
        calls = db_api.get_delayed_calls_to_start(get_time_delay(10))

        self.assertEqual(0, len(calls))

        db_api.delete_delayed_call(call.id)

    @mock.patch.object(db_api, 'update_delayed_call')
    def test_scheduler_doesnt_handle_calls_the_failed_on_update(
            self,
            update_delayed_call):
        def update_call_failed(id, values, query_filter):
            self.queue.put("item")

            return None, 0

        update_delayed_call.side_effect = update_call_failed

        job = sched_base.SchedulerJob(
            run_after=DELAY,
            func_name=TARGET_METHOD_PATH,
            func_args={'name': 'task', 'id': '321'},
        )

        self.scheduler.schedule(job)

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        self.queue.get()

        time.sleep(1)

        update_delayed_call.assert_called_with(
            id=calls[0].id,
            values=mock.ANY,
            query_filter=mock.ANY
        )

        # If the scheduler does handel calls that failed on update
        # DBEntityNotFoundException will raise.
        db_api.get_delayed_call(calls[0].id)
        db_api.delete_delayed_call(calls[0].id)

    def test_scheduler_with_custom_batch_size(self):
        self.scheduler.stop()

        number_delayed_calls = 5
        processed_calls_at_time = []
        real_delete_calls_method = \
            legacy_scheduler.LegacyScheduler.delete_calls

        @staticmethod
        def delete_calls_counter(delayed_calls):
            real_delete_calls_method(delayed_calls)

            for _ in range(len(delayed_calls)):
                self.queue.put("item")

            processed_calls_at_time.append(len(delayed_calls))

        legacy_scheduler.LegacyScheduler.delete_calls = delete_calls_counter

        # Create 5 delayed calls.
        for i in range(number_delayed_calls):
            job = sched_base.SchedulerJob(
                run_after=DELAY,
                func_name=TARGET_METHOD_PATH,
                func_args={'name': 'task', 'id': i},
            )

            self.scheduler.schedule(job)

        # Start scheduler which process 2 calls at a time.
        self.override_config('batch_size', 2, 'scheduler')

        self.scheduler = legacy_scheduler.LegacyScheduler(CONF.scheduler)
        self.scheduler.start()

        # Wait when all of calls will be processed
        for _ in range(number_delayed_calls):
            self.queue.get()

        self.assertListEqual([1, 2, 2], sorted(processed_calls_at_time))
