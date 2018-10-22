# Copyright 2018 Nokia Networks. All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslotest import base

from mistral.api.controllers.v2 import resources


class TestResourceList(base.BaseTestCase):

    def test_next_link_correctness(self):
        task = resources.Task.sample()

        result = resources.Tasks.convert_with_links(
            resources=[task],
            limit=1,
            url='https://localhost:8080',
            sort_keys='created_at,id',
            sort_dirs='asc,asc',
            fields='',
            state='eq:RUNNING'
        )

        next_link = result.next

        self.assertIn('state=eq:RUNNING', next_link)
        self.assertIn('sort_keys=created_at,id', next_link)
