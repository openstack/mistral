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

from mistral.actions import action_factory as a_f
from mistral.engine1 import base
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)
WORKFLOW_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


class DefaultExecutor(base.Executor):
    def __init__(self, engine_client):
        self._engine_client = engine_client

    def run_action(self, task_id, action_class_str, attributes, action_params):
        """Runs action.

        :param task_id: Corresponding task id.
        :param action_class_str: Path to action class in dot notation.
        :param attributes: Attributes of action class which will be set to.
        :param action_params: Action parameters.
        """

        action_cls = a_f.construct_action_class(action_class_str, attributes)

        try:
            action = action_cls(**action_params)

            result = action.run()

            if action.is_sync():
                self._engine_client.on_task_result(
                    task_id,
                    wf_utils.TaskResult(data=result)
                )
        except exc.ActionException as e:
            LOG.exception(
                "Failed to run action [task_id=%s, action_cls='%s',"
                " params='%s']\n %s" %
                (task_id, action_cls, action_params, e)
            )

            self._engine_client.on_task_result(
                task_id,
                wf_utils.TaskResult(error=str(e))
            )
