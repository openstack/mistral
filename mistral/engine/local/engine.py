# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mistral import exceptions as exc
from mistral.engine import abstract_engine as abs_eng
from mistral.engine import states
from mistral.engine.actions import action_factory as a_f
from mistral.engine.actions import action_helper as a_h
from mistral.db import api as db_api
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class LocalEngine(abs_eng.AbstractEngine):
    @classmethod
    def _run_tasks(cls, tasks):
        LOG.info("Workflow is running, tasks to run: %s" % tasks)
        for t in tasks:
            cls._run_task(t)

    @classmethod
    def _run_task(cls, task):
        action = a_f.create_action(task)

        LOG.info("Task is started - %s" % task['name'])

        if a_h.is_task_synchronous(task):
            try:
                state, result = states.SUCCESS, action.run()
            except exc.ActionException:
                state, result = states.ERROR, None

            cls.convey_task_result(task['workbook_name'],
                                   task['execution_id'],
                                   task['id'],
                                   state, result)
        else:
            try:
                action.run()

                db_api.task_update(task['workbook_name'],
                                   task['execution_id'],
                                   task['id'],
                                   {'state': states.RUNNING})
            except exc.ActionException:
                cls.convey_task_result(task['workbook_name'],
                                       task['execution_id'],
                                       task['id'],
                                       states.ERROR, None)


def get_engine():
    return LocalEngine
