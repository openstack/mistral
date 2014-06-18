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

from mistral.db import api as db_api
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.services import trusts


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def evaluate_task_parameters(task, context):
    params = task['task_spec'].get('parameters', {})

    return expr.evaluate_recursively(params, context)


def prepare_tasks(tasks, context):
    for task in tasks:
        # TODO(rakhmerov): Inbound context should be a merge of outbound
        # contexts of task dependencies, if any.
        task['in_context'] = context
        task['parameters'] = evaluate_task_parameters(task, context)

        db_api.task_update(task['id'],
                           {'in_context': task['in_context'],
                            'parameters': task['parameters']})


def get_task_output(task, result):
    publish_transformer = task['task_spec'].get('publish')

    output = expr.evaluate_recursively(publish_transformer, result) or {}

    if result:
        output['task'] = {task['name']: result}

    return output


def _merge_dicts(target, src):
    for key in src:
        # TODO(nmakhotkin) Take care of the same key in both dicts
        to_merge = (key in target
                    and isinstance(target[key], dict)
                    and isinstance(src[key], dict))
        if to_merge:
            _merge_dicts(target[key], src[key])
        else:
            target[key] = src[key]
    return target


def get_outbound_context(task, output=None):
    in_context = task.get('in_context')

    out_context = in_context.copy() if in_context else {}

    if not output:
        output = task.get('output')

    if output:
        out_context = _merge_dicts(out_context, output)

    return out_context


def add_openstack_data_to_context(context, db_workbook):
    if context is None:
        context = {}

    if CONF.pecan.auth_enable:
        workbook_ctx = trusts.create_context(db_workbook)
        if workbook_ctx:
            context.update({'openstack': workbook_ctx.to_dict()})

    return context


def add_execution_to_context(context, db_execution):
    if context is None:
        context = {}

    context['__execution'] = {
        'id': db_execution['id'],
        'workbook_name': db_execution['workbook_name'],
        'task': db_execution['task']
    }

    return context
