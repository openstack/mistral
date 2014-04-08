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


def create_action(db_task):
    # TODO: Implement
    return None


# Registering standard actions on module load.
_register_standard_action_classes()
