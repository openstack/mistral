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

from mistral.actions import base
from mistral.actions import std_actions
from mistral import exceptions as exc

_STD_NAMESPACE = "std"

_NAMESPACES = {}


def _find_or_create_namespace(name):
    ns = _NAMESPACES.get(name)

    if not ns:
        ns = base.Namespace(name)
        _NAMESPACES[name] = ns

    return ns


def register_action_class(namespace_name, action_name, action_cls):
    _find_or_create_namespace(namespace_name).add(action_name, action_cls)


def get_registered_namespaces():
    return _NAMESPACES.copy()


def _register_standard_action_classes():
    register_action_class(_STD_NAMESPACE, "echo", std_actions.EchoAction)
    register_action_class(_STD_NAMESPACE, "http", std_actions.HTTPAction)
    register_action_class(_STD_NAMESPACE, "email", std_actions.SendEmailAction)


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


def create_action(db_task):
    # TODO: Take care of ad-hoc actions.
    action_cls = get_action_class(db_task['task_spec']['action'])

    try:
        action = action_cls(**db_task['parameters'].copy())
    except Exception as e:
        raise exc.ActionException('Failed to create action [db_task=%s]: %s' %
                                  (db_task, e))

    return action


# Registering standard actions on module load.
_register_standard_action_classes()
