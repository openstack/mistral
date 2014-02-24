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

from mistral.db import api as db_api
from mistral.engine import expressions as expr

from mistral.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def evaluate_task_input(task, context):
    res = {}

    params = task['task_dsl'].get('input', {})

    if not params:
        return res

    for name, val in params.iteritems():
        if expr.is_expression(val):
            res[name] = expr.evaluate(val, context)
        else:
            res[name] = val

    return res


def prepare_tasks(tasks, context):
    for task in tasks:
        # TODO(rakhmerov): Inbound context should be a merge of outbound
        # contexts of task dependencies, if any.
        task['in_context'] = context
        task['input'] = evaluate_task_input(task, context)

        db_api.task_update(task['workbook_name'],
                           task['execution_id'],
                           task['id'],
                           {'in_context': task['in_context'],
                            'input': task['input']})


def merge_into_context(context, values):
    if not context:
        return None

    # TODO(rakhmerov): Take care of nested variables.
    context.update(values)

    return context
