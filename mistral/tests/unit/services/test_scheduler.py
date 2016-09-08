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

from mistral import context as auth_context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import scheduler
from mistral.tests.unit import base
from mistral.workflow import utils as wf_utils


FACTORY_METHOD_PATH = (
    'mistral.tests.unit.services.test_scheduler.factory_method'
)
TARGET_METHOD_PATH = (
    'mistral.tests.unit.services.test_scheduler.target_method'
)
CHECK_CONTEXT_METHOD_PATH = (
    'mistral.tests.unit.services.test_scheduler.target_check_context_method'
)
COMPARE_CONTEXT_METHOD_PATH = (
    'mistral.tests.unit.services.test_scheduler.compare_context_values'
)
FAILED_TO_SEND_TARGET_PATH = (
    'mistral.tests.unit.services.test_scheduler.failed_to_send'
)

DELAY = 1.5
WAIT = DELAY * 3


def factory_method():
    return type(
        'something',
        (object,),
        {'run_something': lambda name, id: id}
    )


def target_method():
    pass


def compare_context_values(expected, actual):
    pass


def target_check_context_method(expected_project_id):
    actual_project_id = auth_context.ctx()._BaseContext__values['project_id']
    compare_context_values(expected_project_id, actual_project_id)


def failed_to_send():
    raise exc.EngineException("Test")


def update_call_failed(id, values, query_filter):
    return None, 0


MOCK_UPDATE_CALL_FAILED = mock.MagicMock(side_effect=update_call_failed)


class SchedulerServiceTest(base.DbTestCase):
    def setUp(self):
        super(SchedulerServiceTest, self).setUp()

        self.thread_group = scheduler.setup()

        self.addCleanup(self.thread_group.stop)

    @mock.patch(FACTORY_METHOD_PATH)
    def test_scheduler_with_factory(self, factory):
        target_method = 'run_something'
        method_args = {'name': 'task', 'id': '123'}

        scheduler.schedule_call(
            FACTORY_METHOD_PATH,
            target_method,
            DELAY,
            **method_args
        )

        calls = db_api.get_delayed_calls_to_start(
            datetime.datetime.now() + datetime.timedelta(seconds=2)
        )

        call = self._assert_single_item(
            calls,
            target_method_name=target_method
        )

        self.assertIn('name', call['method_arguments'])

        eventlet.sleep(WAIT)

        factory().run_something.assert_called_once_with(name='task', id='123')

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=1)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self.assertEqual(0, len(calls))

    @mock.patch(FACTORY_METHOD_PATH)
    def test_scheduler_without_factory(self, method):
        method_args = {'name': 'task', 'id': '321'}

        scheduler.schedule_call(
            None,
            FACTORY_METHOD_PATH,
            DELAY,
            **method_args
        )

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=2)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        call = self._assert_single_item(
            calls,
            target_method_name=FACTORY_METHOD_PATH
        )

        self.assertIn('name', call['method_arguments'])

        eventlet.sleep(WAIT)

        method.assert_called_once_with(name='task', id='321')

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=1)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self.assertEqual(0, len(calls))

    @mock.patch(COMPARE_CONTEXT_METHOD_PATH)
    def test_scheduler_call_target_method_with_correct_auth(self, method):
        default_context = base.get_context(default=True)
        auth_context.set_ctx(default_context)
        default_project_id = (
            default_context._BaseContext__values['project_id']
        )
        method_args1 = {'expected_project_id': default_project_id}

        scheduler.schedule_call(
            None,
            CHECK_CONTEXT_METHOD_PATH,
            DELAY,
            **method_args1
        )

        second_context = base.get_context(default=False)
        auth_context.set_ctx(second_context)
        second_project_id = (
            second_context._BaseContext__values['project_id']
        )
        method_args2 = {'expected_project_id': second_project_id}

        scheduler.schedule_call(
            None,
            CHECK_CONTEXT_METHOD_PATH,
            DELAY,
            **method_args2
        )

        eventlet.sleep(WAIT)

        method.assert_any_call(
            default_project_id,
            default_project_id
        )

        method.assert_any_call(
            second_project_id,
            second_project_id
        )

        self.assertNotEqual(default_project_id, second_project_id)

    @mock.patch(FACTORY_METHOD_PATH)
    def test_scheduler_with_serializer(self, factory):
        target_method = 'run_something'

        task_result = wf_utils.Result('data', 'error')

        method_args = {
            'name': 'task',
            'id': '123',
            'result': task_result
        }

        serializers = {
            'result': 'mistral.workflow.utils.ResultSerializer'
        }

        scheduler.schedule_call(
            FACTORY_METHOD_PATH,
            target_method,
            DELAY,
            serializers=serializers,
            **method_args
        )

        calls = db_api.get_delayed_calls_to_start(
            datetime.datetime.now() + datetime.timedelta(seconds=WAIT)
        )

        call = self._assert_single_item(
            calls,
            target_method_name=target_method
        )

        self.assertIn('name', call['method_arguments'])

        eventlet.sleep(WAIT)

        result = factory().run_something.call_args[1].get('result')

        self.assertIsInstance(result, wf_utils.Result)
        self.assertEqual('data', result.data)
        self.assertEqual('error', result.error)

        calls = db_api.get_delayed_calls_to_start(
            datetime.datetime.now() + datetime.timedelta(seconds=1)
        )

        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_PATH)
    def test_scheduler_multi_instance(self, method):
        def stop_thread_groups():
            [tg.stop() for tg in self.tgs]

        self.tgs = [scheduler.setup(), scheduler.setup()]
        self.addCleanup(stop_thread_groups)

        method_args = {'name': 'task', 'id': '321'}

        scheduler.schedule_call(
            None,
            TARGET_METHOD_PATH,
            DELAY,
            **method_args
        )

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=2)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self._assert_single_item(calls, target_method_name=TARGET_METHOD_PATH)

        eventlet.sleep(WAIT)

        method.assert_called_once_with(name='task', id='321')

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=1)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self.assertEqual(0, len(calls))

    @mock.patch(FACTORY_METHOD_PATH)
    def test_scheduler_delete_calls(self, method):
        method_args = {'name': 'task', 'id': '321'}

        scheduler.schedule_call(
            None,
            FACTORY_METHOD_PATH,
            DELAY,
            **method_args
        )

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=2)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self._assert_single_item(calls, target_method_name=FACTORY_METHOD_PATH)

        eventlet.sleep(WAIT)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_delayed_call,
            calls[0].id
        )

    @mock.patch(FACTORY_METHOD_PATH)
    def test_processing_true_does_not_return_in_get_delayed_calls_to_start(
            self,
            method):
        execution_time = (datetime.datetime.now() +
                          datetime.timedelta(seconds=DELAY))

        values = {
            'factory_method_path': None,
            'target_method_name': FACTORY_METHOD_PATH,
            'execution_time': execution_time,
            'auth_context': None,
            'serializers': None,
            'method_arguments': None,
            'processing': True
        }

        call = db_api.create_delayed_call(values)
        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=10)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self.assertEqual(0, len(calls))

        db_api.delete_delayed_call(call.id)

    @mock.patch.object(db_api, 'update_delayed_call', MOCK_UPDATE_CALL_FAILED)
    def test_scheduler_doesnt_handle_calls_the_failed_on_update(self):
        method_args = {'name': 'task', 'id': '321'}

        scheduler.schedule_call(
            None,
            FACTORY_METHOD_PATH,
            DELAY,
            **method_args
        )

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=2)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        eventlet.sleep(WAIT)

        # If the scheduler does handel calls that failed on update
        # DBEntityNotFoundException will raise.
        db_api.get_delayed_call(calls[0].id)

        db_api.delete_delayed_call(calls[0].id)
