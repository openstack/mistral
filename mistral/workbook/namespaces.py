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

from mistral.workbook import actions
from mistral.workbook import base


def merge_dicts(left, right):
    for k, v in right.iteritems():
        if k not in left:
            left[k] = v
        else:
            left_v = left[k]

            if isinstance(left_v, dict) and isinstance(v, dict):
                merge_dicts(left_v, v)


def merge_base_parameters(action, ns_base_parameters):
    if not ns_base_parameters:
        return

    if 'base-parameters' not in action:
        action['base-parameters'] = ns_base_parameters
        return

    action_base_parameters = action['base-parameters']

    merge_dicts(action_base_parameters, ns_base_parameters)


class NamespaceSpec(base.BaseSpec):
    _required_keys = ['name', 'actions']

    def __init__(self, namespace):
        super(NamespaceSpec, self).__init__(namespace)

        if self.validate():
            self.name = namespace['name']
            self.clazz = namespace.get('class')
            self.base_parameters = namespace.get('base-parameters')
            self.parameters = namespace.get('parameters')

            for _, action in namespace['actions'].iteritems():
                action['namespace'] = self.name

                if 'class' not in action:
                    action['class'] = self.clazz

                merge_base_parameters(action, self.base_parameters)

            self.actions = actions.ActionSpecList(namespace['actions'])


class NamespaceSpecList(base.BaseSpecList):
    item_class = NamespaceSpec
