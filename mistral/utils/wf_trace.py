# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 - Mirantis, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from oslo_config import cfg
from oslo_log import log as logging

from mistral.db.v2.sqlalchemy import models

cfg.CONF.import_opt('workflow_trace_log_name', 'mistral.config')
WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


def info(obj, msg, *args, **kvargs):
    """Logs workflow trace record for Execution or Task.

    :param obj: If type is TaskExecution or WorkflowExecution,
        appends execution_id and task_id to the log message.

    The rest of parameters follow logger.info(...)
    """
    debug_info = ''

    if type(obj) is models.TaskExecution:
        exec_id = obj.workflow_execution_id
        task_id = obj.id
        debug_info = '(execution_id=%s task_id=%s)' % (exec_id, task_id)
    elif type(obj) is models.WorkflowExecution:
        debug_info = '(execution_id=%s)' % obj.id

    msg = '%s %s' % (msg, debug_info)

    WF_TRACE.info(msg, *args, **kvargs)
