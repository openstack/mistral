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

from mistral.engine1 import policies
from mistral.openstack.common import log as logging
from mistral.tests.unit.engine1 import base
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)


WORKBOOK = """
---
Version: '2.0'

Workflows:
  wf1:
    type: direct
    start-task: task1

    tasks:
      task1:
        action: std.echo output="Hi!"
        policies:
          wait-before: 2
          wait-after: 5
          retry:
            count: 5
            delay: 10
            break-on: $.my_val = 10
"""


class PoliciesTest(base.EngineTestCase):
    def setUp(self):
        super(PoliciesTest, self).setUp()

        wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)

        self.task_spec = wb_spec.get_workflows()['wf1'].get_tasks()['task1']

    def test_build_policies(self):
        arr = policies.build_policies(self.task_spec.get_policies())

        self.assertEqual(3, len(arr))

        p = self._assert_single_item(arr, delay=2)

        self.assertIsInstance(p, policies.WaitBeforePolicy)

        p = self._assert_single_item(arr, delay=5)

        self.assertIsInstance(p, policies.WaitAfterPolicy)

        p = self._assert_single_item(arr, delay=10)

        self.assertIsInstance(p, policies.RetryPolicy)
        self.assertEqual(5, p.count)
        self.assertEqual('$.my_val = 10', p.break_on)
