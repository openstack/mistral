# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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

import inspect
from oslo.config import cfg

from mistral.actions import base
from mistral.actions import std_actions
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.workbook import actions
from mistral.workbook import tasks

LOG = logging.getLogger(__name__)

_ACTION_CTX_PARAM = 'action_context'
_NAMESPACES = {}


def _find_or_create_namespace(full_name):
    name = full_name.split('.')[-1]
    ns = _NAMESPACES.get(name)

    if not ns:
        ns = base.Namespace(full_name)
        _NAMESPACES[name] = ns

    return ns


def get_registered_namespaces():
    return _NAMESPACES.copy()


def _register_action_classes():
    cfg.CONF.import_opt('action_plugins', 'mistral.config')
    for py_ns in cfg.CONF.action_plugins:
        ns = _find_or_create_namespace(py_ns)
        ns.log()


def get_action_class(action_full_name):
    """Finds action class by full action name (i.e. 'namespace.action_name').

    :param action_full_name: Full action name (that includes namespace).
    :return: Action class or None if not found.
    """
    arr = action_full_name.split('.')

    if len(arr) != 2:
        raise exc.ActionException('Invalid action name: %s' %
                                  action_full_name)

    ns = _NAMESPACES.get(arr[0])

    if not ns:
        return None

    return ns.get_action_class(arr[1])


def _get_action_context(db_task, openstack_context):
    result = {
        'workbook_name': db_task['workbook_name'],
        'execution_id': db_task['execution_id'],
        'task_id': db_task['id'],
        'task_name': db_task['name'],
        'task_tags': db_task['tags'],
    }

    if openstack_context:
        result.update({'openstack': openstack_context})

    return result


def _has_action_context_param(action_cls):
    arg_spec = inspect.getargspec(action_cls.__init__)

    return _ACTION_CTX_PARAM in arg_spec.args


def _create_adhoc_action(db_task, openstack_context):
    task_spec = tasks.TaskSpec(db_task['task_spec'])
    full_action_name = task_spec.get_full_action_name()

    # TODO(rakhmerov): Fix model attributes during refactoring.
    raw_action_spec = db_task['action_spec']

    if not raw_action_spec:
        return None

    action_spec = actions.ActionSpec(raw_action_spec)

    LOG.info('Using ad-hoc action [action=%s, db_task=%s]' %
             (full_action_name, db_task))

    # Create an ad-hoc action.
    base_cls = get_action_class(action_spec.clazz)

    action_context = None
    if _has_action_context_param(base_cls):
        action_context = _get_action_context(db_task, openstack_context)

    if not base_cls:
        msg = 'Ad-hoc action base class is not registered ' \
              '[workbook_name=%s, action=%s, base_class=%s]' % \
              (db_task['workbook_name'], full_action_name, base_cls)
        raise exc.ActionException(msg)

    action_params = db_task['parameters'] or {}

    return std_actions.AdHocAction(action_context,
                                   base_cls,
                                   action_spec,
                                   **action_params)


def create_action(db_task):
    task_spec = tasks.TaskSpec(db_task['task_spec'])
    full_action_name = task_spec.get_full_action_name()

    action_cls = get_action_class(full_action_name)

    openstack_ctx = db_task['in_context'].get('openstack')

    if not action_cls:
        # If action is not found in registered actions try to find ad-hoc
        # action definition.
        if openstack_ctx is not None:
            db_task['parameters'].update({'openstack': openstack_ctx})
        action = _create_adhoc_action(db_task, openstack_ctx)

        if action:
            return action
        else:
            msg = 'Unknown action [workbook_name=%s, action=%s]' % \
                  (db_task['workbook_name'], full_action_name)
            raise exc.ActionException(msg)

    action_params = db_task['parameters'] or {}

    if _has_action_context_param(action_cls):
        action_params[_ACTION_CTX_PARAM] = _get_action_context(db_task,
                                                               openstack_ctx)

    try:
        return action_cls(**action_params)
    except Exception as e:
        raise exc.ActionException('Failed to create action [db_task=%s]: %s' %
                                  (db_task, e))


# Registering actions on module load.
_register_action_classes()
