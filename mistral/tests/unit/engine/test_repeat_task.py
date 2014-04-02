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

from mistral.db import api as db_api
from mistral.tests import base
from mistral.engine.local import engine
from oslo.config import cfg
from mistral.openstack.common import importutils

# We need to make sure that all configuration properties are registered.
importutils.import_module("mistral.config")
cfg.CONF.pecan.auth_enable = False

ENGINE = engine.get_engine()


def create_workbook(workbook_name, definition_path):
    return db_api.workbook_create({
        'name': workbook_name,
        'definition': base.get_resource(definition_path)
    })


class RepeatTaskTest(base.DbTestCase):

    def test_simple_repeat_task(self):
        wb = create_workbook('wb_1', 'repeat_task/single_repeat_task.yaml')
        execution = ENGINE.start_workflow_execution(wb['name'],
                                                    'repeater_task', None)
        tasks = db_api.tasks_get(wb['name'], execution['id'])
        self._assert_single_item(tasks, name='repeater_task')
        self._assert_single_item(tasks, task_runtime_context={
            "iteration_no": 4})

    def test_no_repeat_task(self):
        wb = create_workbook('wb_2', 'repeat_task/no_repeat_task.yaml')
        execution = ENGINE.start_workflow_execution(wb['name'],
                                                    'repeater_task', None)
        tasks = db_api.tasks_get(wb['name'], execution['id'])
        self._assert_single_item(tasks, name='repeater_task')
        self._assert_single_item(tasks, task_runtime_context={
            "iteration_no": -1})

    def test_break_early_repeat_task(self):
        wb = create_workbook('wb_3', 'repeat_task/single_repeat_task.yaml')
        execution = ENGINE.start_workflow_execution(
            wb['name'], 'repeater_task_break_early', None)
        tasks = db_api.tasks_get(wb['name'], execution['id'])
        self._assert_single_item(tasks, name='repeater_task_break_early')
        self._assert_single_item(tasks, task_runtime_context={
            "iteration_no": 0})
