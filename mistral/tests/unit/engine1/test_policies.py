# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

from oslo.config import cfg

from mistral.db.v2 import api as db_api
from mistral.engine import states
from mistral.engine1 import policies
from mistral.openstack.common import log as logging
from mistral.services import scheduler
from mistral.services import workbooks as wb_service
from mistral.tests.unit.engine1 import base
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)
# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')

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


WAIT_BEFORE_WB = """
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
          wait-before: 1
"""


WAIT_AFTER_WB = """
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
          wait-after: 2
"""


RETRY_WB = """
---
Version: '2.0'

Workflows:
  wf1:
    type: direct
    start-task: task1

    tasks:
      task1:
        action: std.http url="http://some_non-existient_host"
        policies:
          retry:
            count: 2
            delay: 2
            break-on: $.my_val = 10
"""


def create_workbook(name, definition):
    return wb_service.create_workbook_v2({
        'name': name,
        'description': 'Simple workbook for testing policies.',
        'definition': definition,
        'tags': ['test']
    })


class PoliciesTest(base.EngineTestCase):
    def setUp(self):
        super(PoliciesTest, self).setUp()

        wb_spec = spec_parser.get_workbook_spec_from_yaml(WORKBOOK)

        self.task_spec = wb_spec.get_workflows()['wf1'].get_tasks()['task1']

        self.wb_name = self.getUniqueString("wb")

        thread_group = scheduler.setup()
        self.addCleanup(thread_group.stop)

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

    def test_wait_before_policy(self):
        create_workbook(self.wb_name, WAIT_BEFORE_WB)

        # Start workflow.
        exec_db = self.engine.start_workflow('%s.wf1' % self.wb_name, {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]
        self.assertEqual(states.DELAYED, task_db.state)
        self.assertIsNone(task_db.runtime_context)

        self._await(
            lambda: self.is_execution_success(exec_db.id),
        )

        exec_db = db_api.get_execution(exec_db.id)

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.SUCCESS, exec_db.state)

    def test_wait_after_policy(self):
        create_workbook(self.wb_name, WAIT_AFTER_WB)

        # Start workflow.
        exec_db = self.engine.start_workflow('%s.wf1' % self.wb_name, {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]
        self.assertEqual(states.RUNNING, task_db.state)
        self.assertIsNone(task_db.runtime_context)

        self._await(
            lambda: self.is_task_delayed(task_db.id),
            delay=0.5
        )
        self._await(
            lambda: self.is_task_success(task_db.id),
        )

        exec_db = db_api.get_execution(exec_db.id)

        self.assertIsNotNone(exec_db)
        self.assertEqual(states.SUCCESS, exec_db.state)

    def test_retry_policy(self):
        create_workbook(self.wb_name, RETRY_WB)

        # Start workflow.
        exec_db = self.engine.start_workflow('%s.wf1' % self.wb_name, {})

        # Note: We need to reread execution to access related tasks.
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]
        self.assertEqual(states.RUNNING, task_db.state)
        self.assertIsNone(task_db.runtime_context)

        self._await(
            lambda: self.is_task_delayed(task_db.id),
            delay=0.5
        )
        self._await(
            lambda: self.is_task_error(task_db.id),
        )
        self._await(
            lambda: self.is_execution_error(exec_db.id),
        )
        exec_db = db_api.get_execution(exec_db.id)
        task_db = exec_db.tasks[0]

        self.assertEqual(
            1, task_db.runtime_context["retry_task_policy"]["retry_no"])
        self.assertIsNotNone(exec_db)
        self.assertEqual(states.ERROR, exec_db.state)
