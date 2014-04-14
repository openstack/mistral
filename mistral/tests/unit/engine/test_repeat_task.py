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

from mistral.openstack.common import log as logging
from mistral.openstack.common import importutils
from mistral.tests import base
from mistral.db import api as db_api
from mistral.engine.scalable import engine
from mistral import dsl_parser

# We need to make sure that all configuration properties are registered.
importutils.import_module("mistral.config")

LOG = logging.getLogger(__name__)

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


def create_workbook(workbook_name, definition_path):
    return db_api.workbook_create({
        'name': workbook_name,
        'definition': base.get_resource(definition_path)
    })


class RepeatTaskTest(base.EngineTestCase):
    @mock.patch.object(engine.ScalableEngine, '_run_tasks',
                       mock.MagicMock(
                           side_effect=base.EngineTestCase.mock_run_tasks))
    def test_simple_repeat_task(self):
        wb = create_workbook('wb_1', 'repeat_task/single_repeat_task.yaml')
        execution = self.engine.start_workflow_execution(wb['name'],
                                                         'repeater_task', None)
        wb_spec = dsl_parser.get_workbook(wb['definition'])
        iterations, _, delay = wb_spec.tasks.get('repeater_task').\
            get_repeat_task_parameters()

        # Wait until all iterations are finished
        eventlet.sleep(delay * iterations + 1)
        tasks = db_api.tasks_get(wb['name'], execution['id'])
        self._assert_single_item(tasks, name='repeater_task')
        self._assert_single_item(tasks, task_runtime_context={
            "iteration_no": 2})

    @mock.patch.object(engine.ScalableEngine, '_run_tasks',
                       mock.MagicMock(
                           side_effect=base.EngineTestCase.mock_run_tasks))
    def test_no_repeat_task(self):
        wb = create_workbook('wb_2', 'repeat_task/no_repeat_task.yaml')
        execution = self.engine.start_workflow_execution(wb['name'],
                                                         'repeater_task', None)
        tasks = db_api.tasks_get(wb['name'], execution['id'])
        self._assert_single_item(tasks, name='repeater_task')
        self._assert_single_item(tasks, task_runtime_context={
            "iteration_no": -1})

    @mock.patch.object(engine.ScalableEngine, '_run_tasks',
                       mock.MagicMock(
                           side_effect=base.EngineTestCase.mock_run_tasks))
    def test_break_early_repeat_task(self):
        wb = create_workbook('wb_3', 'repeat_task/single_repeat_task.yaml')
        execution = self.engine.start_workflow_execution(
            wb['name'], 'repeater_task_break_early', None)
        tasks = db_api.tasks_get(wb['name'], execution['id'])
        self._assert_single_item(tasks, name='repeater_task_break_early')
        self._assert_single_item(tasks, task_runtime_context={
            "iteration_no": 0})

    @mock.patch.object(engine.ScalableEngine, '_run_tasks',
                       mock.MagicMock(
                           side_effect=base.EngineTestCase.mock_run_tasks))
    def test_from_no_repeat_to_repeat_task(self):
        wb = create_workbook('wb_4', 'repeat_task/single_repeat_task.yaml')
        execution = self.engine.start_workflow_execution(
            wb['name'], 'not_repeat_task', None)
        wb_spec = dsl_parser.get_workbook(wb['definition'])
        iterations, _, delay = wb_spec.tasks.get('repeater_task').\
            get_repeat_task_parameters()

        # Wait until all iterations are finished
        eventlet.sleep(delay * iterations + 1)
        tasks = db_api.tasks_get(wb['name'], execution['id'])

        self._assert_multiple_items(tasks, 2)
        self._assert_single_item(tasks, name='repeater_task')
        self._assert_single_item(tasks, task_runtime_context=None)
