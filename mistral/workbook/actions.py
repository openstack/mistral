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

from mistral.workbook import base


class ActionSpec(base.BaseSpec):
    _required_keys = ['name', 'class', 'namespace']

    def __init__(self, action):
        super(ActionSpec, self).__init__(action)

        if self.validate():
            self.name = action['name']
            self.clazz = action['class']
            self.namespace = action['namespace']
            self.base_parameters = action.get('base-parameters', {})
            self.parameters = action.get('parameters', {})
            self.output = action.get('output', {})


class ActionSpecList(base.BaseSpecList):
    item_class = ActionSpec
