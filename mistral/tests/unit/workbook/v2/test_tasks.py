# Copyright 2015 - Huawei Technologies Co. Ltd
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

from mistral import exceptions
from mistral.tests import base
from mistral.workbook.v2 import tasks


class TaskSpecListTest(base.BaseTest):
    def test_get_class(self):
        spec_list_cls = tasks.TaskSpecList.get_class('direct')

        self.assertIs(spec_list_cls, tasks.DirectWfTaskSpecList)

    def test_get_class_notfound(self):
        exc = self.assertRaises(
            exceptions.NotFoundException,
            tasks.TaskSpecList.get_class,
            "invalid"
        )

        self.assertIn("Can not find task list specification", str(exc))
