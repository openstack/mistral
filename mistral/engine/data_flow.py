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

import inspect
from oslo.config import cfg

from mistral.db.v1 import api as db_api
from mistral.engine import states
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.services import action_manager as a_m
from mistral.services import security
from mistral.workbook import parser as spec_parser


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

_ACTION_CTX_PARAM = 'action_context'


def _has_action_context_param(action_cls):
    arg_spec = inspect.getargspec(action_cls.__init__)

    return _ACTION_CTX_PARAM in arg_spec.args


def _get_action_context(db_task, openstack_context):
    result = {
        'workbook_name': db_task.workbook_name,
        'execution_id': db_task.execution_id,
        'task_id': db_task.id,
        'task_name': db_task.name,
        'task_tags': db_task.tags,
    }

    if openstack_context:
        result.update({'openstack': openstack_context})

    return result


def evaluate_task_parameters(task_db, context):
    params = task_db.task_spec.get('parameters', {})

    return expr.evaluate_recursively(params, context)


def build_required_context(task, tasks):
    context = {}

    for req_task in tasks:
        dep_ids = task.requires or []

        if req_task.id in dep_ids:
            _merge_dicts(context, get_outbound_context(req_task))

    return context


def prepare_tasks(tasks_to_start, context, workbook, tasks):
    results = []

    for task in tasks_to_start:
        context = _merge_dicts(context, build_required_context(task, tasks))

        action_params = evaluate_task_parameters(task, context)

        db_api.task_update(task.id,
                           {'state': states.RUNNING,
                            'in_context': context,
                            'parameters': action_params})

        # Get action name. Unwrap ad-hoc and reevaluate params if
        # necessary.
        action_name = spec_parser.get_task_spec(task.task_spec)\
            .get_full_action_name()

        openstack_ctx = context.get('openstack')

        if not a_m.get_action_class(action_name):
            # If action is not found in registered actions try to find
            # ad-hoc action definition.
            if openstack_ctx is not None:
                action_params.update({'openstack': openstack_ctx})

            action = a_m.resolve_adhoc_action_name(workbook, action_name)

            if not action:
                msg = 'Unknown action [workbook=%s, action=%s]' % \
                      (workbook, action_name)
                raise exc.ActionException(msg)

            action_params = a_m.convert_adhoc_action_params(workbook,
                                                            action_name,
                                                            action_params)
            action_name = action

        if _has_action_context_param(a_m.get_action_class(action_name)):
            action_params[_ACTION_CTX_PARAM] = \
                _get_action_context(task, openstack_ctx)

        results.append((task.id, action_name, action_params))

    return results


def get_task_output(task, result):
    publish_transformer = task.task_spec.get('publish')

    output = expr.evaluate_recursively(publish_transformer, result) or {}

    if result:
        output['task'] = {task.name: result}

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
    in_context = task.in_context

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
        workbook_ctx = security.create_context(
            db_workbook.trust_id, db_workbook.project_id
        )

        if workbook_ctx:
            context.update({'openstack': workbook_ctx.to_dict()})

    return context


def add_execution_to_context(context, db_execution):
    if context is None:
        context = {}

    context['__execution'] = {
        'id': db_execution.id,
        'workbook_name': db_execution['workbook_name'],
        'task': db_execution.task
    }

    return context
