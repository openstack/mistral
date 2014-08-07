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

# TODO(rakhmerov): Module needs to be fully reviewed and refactored

import copy
import itertools
from oslo.config import cfg

from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.services import trusts
from mistral import utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


# TODO(rakhmerov): How to take this into account correctly?
# The problem is that dependencies is a responsibility of reverse
# workflow handler.
def build_required_context(task, tasks):
    context = {}

    for req_task in tasks:
        dep_ids = task.requires or []

        if req_task.id in dep_ids:
            utils.merge_dicts(context, evaluate_outbound_context(req_task))

    return context


def evaluate_task_parameters(task_spec, context):
    return expr.evaluate_recursively(task_spec.get_parameters(), context)


def prepare_db_tasks(db_tasks, task_specs, context):
    """Prepare Data Flow properties ('in_context' and 'parameters')
     of given DB tasks.

    :param db_tasks: DB tasks.
    :param task_specs: Task specifications.
    :param context: Data Flow context.
    :return:
    """
    # TODO(rakhmerov): Take care of ad-hoc actions.
    for task_db, task_spec in itertools.izip(db_tasks, task_specs):
        task_db.in_context = context
        task_db.parameters = evaluate_task_parameters(task_spec, context)


def evaluate_task_output(task_spec, result):
    """Evaluates task output

    :param task_db: DB task.
    :param task_spec: Task specification
    :param result: Raw task result that comes from action/workflow
        (before publisher).
    :return: Complete task output that goes to Data Flow context.
    """
    publish_transformer = task_spec.get_publish()

    # Evaluate 'publish' clause using raw result as a context.
    output = expr.evaluate_recursively(publish_transformer, result) or {}

    # Add raw task result to task output under key 'task'
    output['task'] = {task_spec.get_name(): result}

    return output


def evaluate_outbound_context(task_db):
    """Evaluates task outbound Data Flow context.

    This method assumes that complete task output (after publisher etc.)
    has already been evaluated.
    :param task_db: DB task.
    :return: Outbound task Data Flow context.
    """
    return utils.merge_dicts(
        copy.copy(task_db.in_context) or {},
        task_db.output
    )


def add_openstack_data_to_context(workbook_db, context):
    if context is None:
        context = {}

    if CONF.pecan.auth_enable:
        workbook_ctx = trusts.create_context(workbook_db)

        if workbook_ctx:
            context.update({'openstack': workbook_ctx.to_dict()})

    return context


def add_execution_to_context(exec_db, context):
    if context is None:
        context = {}

    context['__execution'] = {
        'id': exec_db.id,
        'wf_spec': exec_db['wf_spec'],
        'start_params': exec_db.start_params,
        'input': exec_db.input
    }

    return context
