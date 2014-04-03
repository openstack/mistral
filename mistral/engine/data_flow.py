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

import six
from oslo.config import cfg

from mistral.db import api as db_api
from mistral.engine import expressions as expr
from mistral.services import trusts
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def evaluate_task_input(task, context):
    res = {}

    params = task['task_spec'].get('input', {})

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


def get_task_output(task, result):
    vars_to_publish = task['task_spec'].get('publish')

    output = {}

    if result:
        output['task'] = {task['name']: result}

        # TODO(rakhmerov): Take care of nested variables.
        if vars_to_publish:
            for var_name, res_var_name in vars_to_publish.iteritems():
                output[var_name] = result[res_var_name]

    return output


def get_outbound_context(task, output=None):
    in_context = task.get('in_context')

    out_context = in_context.copy() if in_context else {}

    if not output:
        output = task.get('output')

    if output:
        out_context.update(output)

    return out_context


def add_token_to_context(context, db_workbook):
    if context is None:
        context = {}
    if CONF.pecan.auth_enable:
        workbook_ctx = trusts.create_context(db_workbook)
        if workbook_ctx:
            context.update(workbook_ctx.to_dict())
    return context


def _modify_item(item, context):
    if isinstance(item, six.string_types):
        try:
            return expr.evaluate(item, context)
        except AttributeError as e:
            LOG.debug("Expression %s is not evaluated, [context=%s]: %s"
                      % (item, context, e))
            return item
    else:
        return apply_context(item, context)


def apply_context(data, context):
    if not context:
        return data
    if isinstance(data, dict):
        for key in data:
            data[key] = _modify_item(data[key], context)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            data[index] = _modify_item(item, context)
    return data
