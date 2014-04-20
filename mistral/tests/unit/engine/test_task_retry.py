# -*- coding: utf-8 -*-
#
# Copyright 2014 - StackStorm, Inc.
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

import mock

import eventlet

from oslo.config import cfg

from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.db import api as db_api
from mistral.engine import client
from mistral.engine.scalable import engine
from mistral.actions import std_actions
from mistral.engine import states
from mistral import dsl_parser as parser


LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

WB_NAME = "my_workbook"


def _get_workbook(workbook_name):
    wb = db_api.workbook_get(workbook_name)
    return parser.get_workbook(wb["definition"])


class FailBeforeSuccessMocker(object):
    def __init__(self, fail_count):
        self._max_fail_count = fail_count
        self._call_count = 0

    def mock_partial_failure(self, *args):
        if self._call_count < self._max_fail_count:
            self._call_count += 1
            raise exc.ActionException()

        return "result"


@mock.patch.object(
    client.EngineClient, 'start_workflow_execution',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_start_workflow))
@mock.patch.object(
    client.EngineClient, 'convey_task_result',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_task_result))
@mock.patch.object(
    engine.ScalableEngine, '_run_tasks',
    mock.MagicMock(side_effect=base.EngineTestCase.mock_run_tasks))
@mock.patch.object(
    db_api, 'workbook_get',
    mock.MagicMock(
        return_value={
            'definition': base.get_resource('retry_task/retry_task.yaml')}))
@mock.patch.object(
    std_actions.HTTPAction, 'run',
    mock.MagicMock(return_value='result'))
class TaskRetryTest(base.EngineTestCase):

    def test_no_retry(self):
        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         'retry_task', None)
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks[0]['id'], states.SUCCESS,
                                       {'output': 'result'})

        # TODO(rakhmerov): It's not stable, need to avoid race condition.
        self._assert_single_item(tasks, name='retry_task')
        self._assert_single_item(tasks, task_runtime_context=None)

    def test_retry_always_error(self):
        workbook = _get_workbook(WB_NAME)

        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         'retry_task', None)
        tasks = db_api.tasks_get(WB_NAME, execution['id'])
        task_spec = workbook.tasks.get(tasks[0]['name'])
        retry_count, _, __ = task_spec.get_retry_parameters()

        for x in xrange(0, retry_count + 1):
            self.engine.convey_task_result(WB_NAME, execution['id'],
                                           tasks[0]['id'], states.ERROR,
                                           {'output': 'result'})

        # TODO(rakhmerov): It's not stable, need to avoid race condition.
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, name='retry_task')
        self._assert_single_item(tasks, task_runtime_context={
            'retry_no': retry_count - 1})
        self._assert_single_item(tasks, state=states.ERROR)

    def test_retry_eventual_success(self):
        workbook = _get_workbook(WB_NAME)

        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         'retry_task', None)
        tasks = db_api.tasks_get(WB_NAME, execution['id'])
        task_spec = workbook.tasks.get(tasks[0]['name'])
        retry_count, _, __ = task_spec.get_retry_parameters()

        for x in xrange(0, retry_count/2):
            self.engine.convey_task_result(WB_NAME, execution['id'],
                                           tasks[0]['id'], states.ERROR,
                                           {'output': 'result'})

        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks[0]['id'], states.SUCCESS,
                                       {'output': 'result'})

        # TODO(rakhmerov): It's not stable, need to avoid race condition.
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, name='retry_task')
        self._assert_single_item(tasks, task_runtime_context={
            'retry_no': retry_count/2 - 1})

    def test_retry_delay(self):
        task_name = 'delay_retry_task'
        workbook = _get_workbook(WB_NAME)

        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         task_name, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])
        task_spec = workbook.tasks.get(tasks[0]['name'])
        retry_count, _, delay = task_spec.get_retry_parameters()

        for x in xrange(0, retry_count):
            self.engine.convey_task_result(WB_NAME, execution['id'],
                                           tasks[0]['id'], states.ERROR,
                                           {'output': 'result'})

            tasks = db_api.tasks_get(WB_NAME, execution['id'])

            # TODO(rakhmerov): It's not stable, need to avoid race condition.
            self._assert_single_item(tasks, name=task_name)
            self._assert_single_item(tasks, state=states.DELAYED)

            eventlet.sleep(delay * 2)

        # Convey final result outside the loop.
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks[0]['id'], states.ERROR,
                                       {'output': 'result'})

        # TODO(rakhmerov): It's not stable, need to avoid race condition.
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, name=task_name)
        self._assert_single_item(tasks, task_runtime_context={
            'retry_no': retry_count - 1})
        self._assert_single_item(tasks, state=states.ERROR)

    def test_from_no_retry_to_retry_task(self):
        task_name_1 = 'no_retry_task'
        task_name_2 = 'delay_retry_task'
        workbook = _get_workbook(WB_NAME)

        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         task_name_1, None)

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, name=task_name_1)

        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks[0]['id'], states.SUCCESS,
                                       {'output': 'result'})

        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, name=task_name_2)

        task_spec = workbook.tasks.get(task_name_2)
        retry_count, _, delay = task_spec.get_retry_parameters()

        for x in xrange(0, retry_count):
            self.engine.convey_task_result(WB_NAME, execution['id'],
                                           tasks[1]['id'], states.ERROR,
                                           {'output': 'result'})

            tasks = db_api.tasks_get(WB_NAME, execution['id'])

            # TODO(rakhmerov): It's not stable, need to avoid race condition.
            self._assert_single_item(tasks, name=task_name_1)
            self._assert_single_item(tasks, state=states.DELAYED)

            eventlet.sleep(delay * 2)

        # Convey final result outside the loop.
        self.engine.convey_task_result(WB_NAME, execution['id'],
                                       tasks[1]['id'], states.ERROR,
                                       {'output': 'result'})

        # TODO(rakhmerov): It's not stable, need to avoid race condition.
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, name=task_name_2)
        self._assert_single_item(tasks, task_runtime_context={
            'retry_no': retry_count - 1})
        self._assert_single_item(tasks, state=states.ERROR)

    @mock.patch.object(std_actions.EchoAction, "run",
                       mock.MagicMock(side_effect=exc.ActionException))
    def test_sync_action_always_error(self):
        task_name_1 = 'sync_task'
        workbook = _get_workbook(WB_NAME)
        task_spec = workbook.tasks.get(task_name_1)
        retry_count, _, __ = task_spec.get_retry_parameters()

        execution = self.engine.start_workflow_execution(WB_NAME,
                                                         task_name_1, None)

        # TODO(rakhmerov): It's not stable, need to avoid race condition.
        tasks = db_api.tasks_get(WB_NAME, execution['id'])

        self._assert_single_item(tasks, name=task_name_1)
        self._assert_single_item(tasks, task_runtime_context={
            'retry_no': retry_count - 1})
        self._assert_single_item(tasks, state=states.ERROR)

    def test_sync_action_eventual_success(self):
        task_name_1 = 'sync_task'
        workbook = _get_workbook(WB_NAME)
        task_spec = workbook.tasks.get(task_name_1)
        retry_count, _, __ = task_spec.get_retry_parameters()

        # After a pre-set no of retries the mock method will return a
        # success to simulate this test-case.
        mock_functor = FailBeforeSuccessMocker(retry_count/2 + 1)

        with mock.patch.object(std_actions.EchoAction, "run",
                               side_effect=mock_functor.mock_partial_failure):
            execution = self.engine.start_workflow_execution(WB_NAME,
                                                             task_name_1, None)

            # TODO(rakhmerov): It's not stable, need to avoid race condition.
            tasks = db_api.tasks_get(WB_NAME, execution['id'])

            self._assert_single_item(tasks, name=task_name_1)
            self._assert_single_item(tasks, task_runtime_context={
                'retry_no': retry_count/2})
            self._assert_single_item(tasks, state=states.SUCCESS)
