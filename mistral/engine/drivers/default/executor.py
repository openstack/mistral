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

# TODO(rakhmerov): Deprecated in favor of package 'mistral.engine1'.

from oslo.config import cfg

from mistral.engine import executor
from mistral.engine import states
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import action_manager as a_m


LOG = logging.getLogger(__name__)
WORKFLOW_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


class DefaultExecutor(executor.Executor):
    def _log_action_exception(self, message, task_id, action, params, ex):
        LOG.exception("%s [task_id=%s, action='%s', params='%s']\n %s" %
                      (message, str(task_id), str(action),
                       str(params), str(ex)))

    def handle_task(self, cntx, task_id, action_name, params={}):
        """Handle the execution of the workbook task.

        :param task_id: task identifier
        :type task_id: str
        :param action_name: a name of the action to run
        :type action_name: str
        :param params: a dict of action parameters
        """

        action_cls = a_m.get_action_class(action_name)

        # TODO(dzimine): on failure, convey failure details back
        try:
            action = action_cls(**params)
        except Exception as e:
            raise exc.ActionException("Failed to create action"
                                      "[action_name=%s, params=%s]: %s" %
                                      (action_name, params, e))

        if action.is_sync():
            try:
                state, result = states.SUCCESS, action.run()
            except exc.ActionException as ex:
                self._log_action_exception("Action failed", task_id,
                                           action_name, params, ex)
                state, result = states.ERROR, None

            self.engine.convey_task_result(task_id, state, result)
        else:
            try:
                action.run()
            except exc.ActionException as ex:
                self._log_action_exception("Action failed", task_id,
                                           action_name, params, ex)
                self.engine.convey_task_result(task_id, states.ERROR, None)
