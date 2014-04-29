# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

from oslo.config import cfg

from mistral.openstack.common import log as logging
from mistral.db import api as db_api
from mistral import exceptions as exc
from mistral import engine
from mistral.engine import client
from mistral.engine import states
from mistral.actions import action_factory as a_f


LOG = logging.getLogger(__name__)
WORKFLOW_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


class Executor(object):
    def __init__(self, transport=None):
        self.transport = engine.get_transport(transport)
        self.engine = client.EngineClient(self.transport)

    def _do_task_action(self, task):
        """Executes the action defined by the task and return result.

        :param task: a task definition
        :type task: dict
        """
        LOG.info("Starting task action [task_id=%s, "
                 "action='%s', action_spec='%s'" %
                 (task['id'], task['task_spec']['action'],
                  task['action_spec']))

        action = a_f.create_action(task)

        if action.is_sync():
            try:
                state, result = states.SUCCESS, action.run()
            except exc.ActionException:
                state, result = states.ERROR, None

            self.engine.convey_task_result(task['workbook_name'],
                                           task['execution_id'],
                                           task['id'],
                                           state, result)
        else:
            try:
                action.run()

            except exc.ActionException:
                self.engine.convey_task_result(task['workbook_name'],
                                               task['execution_id'],
                                               task['id'],
                                               states.ERROR, None)

    def _handle_task_error(self, task, exception):
        """Handle exception from the task execution.

        :param task: the task corresponding to the exception
        :type task: dict
        :param exception: an exception thrown during the execution of the task
        :type exception: Exception
        """
        try:
            db_api.start_tx()
            try:
                db_api.execution_update(task['workbook_name'],
                                        task['execution_id'],
                                        {'state': states.ERROR})
                db_api.task_update(task['workbook_name'],
                                   task['execution_id'],
                                   task['id'],
                                   {'state': states.ERROR})
                db_api.commit_tx()
            finally:
                db_api.end_tx()
        except Exception as e:
            LOG.exception(e)

    def handle_task(self, cntx, **kwargs):
        """Handle the execution of the workbook task.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        """
        try:
            task = kwargs.get('task', None)
            if not task:
                raise Exception('No task is provided to the executor.')

            LOG.info("Received a task: %s" % task)

            db_task = db_api.task_get(task['workbook_name'],
                                      task['execution_id'],
                                      task['id'])
            db_exec = db_api.execution_get(task['workbook_name'],
                                           task['execution_id'])

            if not db_exec or not db_task:
                return

            if db_exec['state'] != states.RUNNING or \
                    db_task['state'] != states.IDLE:
                return

            # Update the state to running before performing action. The
            # do_task_action assigns state to the task which is the appropriate
            # value to preserve.

            WORKFLOW_TRACE.info("Task '%s' [%s -> %s]" % (db_task['name'],
                                                          db_task['state'],
                                                          states.RUNNING))

            db_api.task_update(task['workbook_name'],
                               task['execution_id'],
                               task['id'],
                               {'state': states.RUNNING})

            self._do_task_action(db_task)
        except Exception as e:
            LOG.exception(e)
            self._handle_task_error(task, e)
