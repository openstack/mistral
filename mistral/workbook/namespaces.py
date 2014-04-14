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


class NamespaceSpec(base.BaseSpec):
    _required_keys = ['name', 'actions']

    def __init__(self, service):
        super(NamespaceSpec, self).__init__(service)

        if self.validate():
            self.name = service['name']

            for _, action in service['actions'].iteritems():
                action['namespace'] = self.name

            self.actions = actions.ActionSpecList(service['actions'])


class NamespaceSpecList(base.BaseSpecList):
    item_class = NamespaceSpec
