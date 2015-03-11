# Copyright 2014 - Mirantis, Inc.
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

from mistral.db.v2 import api as db_api
from mistral.services import scheduler
from mistral.tests import base
from mistral.workflow import utils as wf_utils


FACTORY_METHOD_NAME = ('mistral.tests.unit.services.test_scheduler.'
                       'factory_method')
TARGET_METHOD_NAME = FACTORY_METHOD_NAME


def factory_method():
    return type(
        'something',
        (object,),
        {'run_something': lambda name, id: id}
    )


class SchedulerServiceTest(base.DbTestCase):
    def setUp(self):
        super(SchedulerServiceTest, self).setUp()

        self.thread_group = scheduler.setup()

        self.addCleanup(self.thread_group.stop)

    @mock.patch(FACTORY_METHOD_NAME)
    def test_scheduler_with_factory(self, factory):
        target_method = 'run_something'
        method_args = {'name': 'task', 'id': '123'}
        delay = 1.5

        scheduler.schedule_call(
            FACTORY_METHOD_NAME,
            target_method,
            delay,
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

        eventlet.sleep(delay)

        factory().run_something.assert_called_once_with(name='task', id='123')

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=1)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_NAME)
    def test_scheduler_without_factory(self, method):
        method_args = {'name': 'task', 'id': '321'}
        delay = 1.5

        scheduler.schedule_call(
            None,
            TARGET_METHOD_NAME,
            delay,
            **method_args
        )

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=2)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        call = self._assert_single_item(
            calls,
            target_method_name=TARGET_METHOD_NAME
        )

        self.assertIn('name', call['method_arguments'])

        eventlet.sleep(delay)

        method.assert_called_once_with(name='task', id='321')

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=1)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self.assertEqual(0, len(calls))

    @mock.patch(FACTORY_METHOD_NAME)
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

        delay = 1.5

        scheduler.schedule_call(
            FACTORY_METHOD_NAME,
            target_method,
            delay,
            serializers=serializers,
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

        eventlet.sleep(delay)

        result = factory().run_something.call_args[1].get('result')

        self.assertIsInstance(result, wf_utils.Result)
        self.assertEqual('data', result.data)
        self.assertEqual('error', result.error)

        calls = db_api.get_delayed_calls_to_start(
            datetime.datetime.now() + datetime.timedelta(seconds=1)
        )

        self.assertEqual(0, len(calls))

    @mock.patch(TARGET_METHOD_NAME)
    def test_scheduler_multi_instance(self, method):
        def stop_thread_groups():
            [tg.stop() for tg in self.tgs]

        self.tgs = [scheduler.setup(), scheduler.setup()]
        self.addCleanup(stop_thread_groups)

        method_args = {'name': 'task', 'id': '321'}
        delay = 1.5

        scheduler.schedule_call(
            None,
            TARGET_METHOD_NAME,
            delay,
            **method_args
        )

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=2)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self._assert_single_item(calls, target_method_name=TARGET_METHOD_NAME)

        eventlet.sleep(delay)

        method.assert_called_once_with(name='task', id='321')

        time_filter = datetime.datetime.now() + datetime.timedelta(seconds=1)
        calls = db_api.get_delayed_calls_to_start(time_filter)

        self.assertEqual(0, len(calls))
