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
import eventlet
import mock

from eventlet import queue
from eventlet import timeout
from mistral import context as auth_context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import scheduler
from mistral.tests.unit import base
from mistral_lib import actions as ml_actions

TARGET_METHOD_PATH = (
    'mistral.tests.unit.services.test_scheduler.target_method'
)
DELAY = 1.5


def get_time_delay(delay=DELAY):
    return datetime.datetime.now() + datetime.timedelta(seconds=delay)


def target_method():
    pass


class SchedulerServiceTest(base.DbTestCase):

    def setUp(self):
        super(SchedulerServiceTest, self).setUp()

        self.timeout = timeout.Timeout(seconds=10)
        self.queue = queue.Queue()

        self.scheduler = scheduler.Scheduler(0, 1, None)
        self.scheduler.start()

        self.addCleanup(self.scheduler.stop, True)
        self.addCleanup(self.timeout.cancel)

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

        scheduler.schedule_call(
            TARGET_METHOD_PATH,
            target_method_name,
            DELAY,
            **{'name': 'task', 'id': '123'}
        )

        calls = db_api.get_delayed_calls_to_start(get_time_delay())
        call = self._assert_single_item(
            calls,
            target_method_name=target_method_name
        )
        self.assertIn('name', call['method_arguments'])

        self.queue.get()
        factory().run_something.assert_called_once_with(name='task', id='123')

        calls = db_api.get_delayed_calls_to_start(get_time_delay())
        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_without_factory(self, method):
        method.side_effect = self.target_method

        scheduler.schedule_call(
            None,
            TARGET_METHOD_PATH,
            DELAY,
            **{'name': 'task', 'id': '321'}
        )

        calls = db_api.get_delayed_calls_to_start(get_time_delay())
        call = self._assert_single_item(
            calls,
            target_method_name=TARGET_METHOD_PATH
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
        default_project_id = (
            default_context.project_id
        )

        scheduler.schedule_call(
            None,
            TARGET_METHOD_PATH,
            DELAY,
            **{'expected_project_id': default_project_id}
        )

        second_context = base.get_context(default=False)
        auth_context.set_ctx(second_context)
        second_project_id = (
            second_context.project_id
        )

        scheduler.schedule_call(
            None,
            TARGET_METHOD_PATH,
            DELAY,
            **{'expected_project_id': second_project_id}
        )

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

        scheduler.schedule_call(
            TARGET_METHOD_PATH,
            target_method_name,
            DELAY,
            serializers=serializers,
            **method_args
        )

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

        second_scheduler = scheduler.Scheduler(1, 1, None)
        second_scheduler.start()
        self.addCleanup(second_scheduler.stop, True)

        scheduler.schedule_call(
            None,
            TARGET_METHOD_PATH,
            DELAY,
            **{'name': 'task', 'id': '321'}
        )

        calls = db_api.get_delayed_calls_to_start(get_time_delay())
        self._assert_single_item(calls, target_method_name=TARGET_METHOD_PATH)

        self.queue.get()
        method.assert_called_once_with(name='task', id='321')

        calls = db_api.get_delayed_calls_to_start(get_time_delay())
        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_delete_calls(self, method):
        method.side_effect = self.target_method

        scheduler.schedule_call(
            None,
            TARGET_METHOD_PATH,
            DELAY,
            **{'name': 'task', 'id': '321'}
        )

        calls = db_api.get_delayed_calls_to_start(get_time_delay())
        self._assert_single_item(calls, target_method_name=TARGET_METHOD_PATH)

        self.queue.get()
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

        scheduler.schedule_call(
            None,
            TARGET_METHOD_PATH,
            DELAY,
            **{'name': 'task', 'id': '321'}
        )

        calls = db_api.get_delayed_calls_to_start(get_time_delay())

        self.queue.get()
        eventlet.sleep(1)

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
        real_delete_calls_method = scheduler.Scheduler.delete_calls

        @staticmethod
        def delete_calls_counter(delayed_calls):
            real_delete_calls_method(delayed_calls)

            for _ in range(len(delayed_calls)):
                self.queue.put("item")
            processed_calls_at_time.append(len(delayed_calls))

        scheduler.Scheduler.delete_calls = delete_calls_counter

        # Create 5 delayed calls
        for i in range(number_delayed_calls):
            scheduler.schedule_call(
                None,
                TARGET_METHOD_PATH,
                0,
                **{'name': 'task', 'id': i}
            )

        # Start scheduler which process 2 calls at a time
        self.scheduler = scheduler.Scheduler(0, 1, 2)
        self.scheduler.start()

        # Wait when all of calls will be processed
        for _ in range(number_delayed_calls):
            self.queue.get()

        self.assertEqual(
            [2, 2, 1],
            processed_calls_at_time
        )
