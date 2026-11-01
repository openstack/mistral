# Copyright 2026 - OVHcloud
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

from unittest import mock

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral.services import security
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base

WB = """
---
version: '2.0'

parent:
  tasks:
    task1:
      workflow: child

child:
  tasks:
    task1:
      action: std.noop
"""


class ExecutionTrustTest(base.EngineTestCase):
    def setUp(self):
        super(ExecutionTrustTest, self).setUp()

        wf_service.create_workflows(WB)

    def _start(self, execution_trust):
        ctx = auth_ctx.ctx()
        ctx.trust_id = 'trust-1' if execution_trust else None
        ctx.execution_trust = execution_trust

        return self.engine.start_workflow('parent')

    @mock.patch.object(security, 'delete_trust')
    def test_trust_deleted_when_root_completes(self, m_delete):
        wf_ex = self._start(execution_trust=True)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_execs = db_api.get_workflow_executions()
            contexts = {ex.name: ex.runtime_context for ex in wf_execs}

        self.assertEqual(
            'trust-1', contexts['parent'].get('execution_trust_id')
        )
        self.assertNotIn('execution_trust_id', contexts['child'])

        self._await(lambda: m_delete.call_count > 0)
        m_delete.assert_called_once_with('trust-1')

    @mock.patch.object(security, 'delete_trust')
    def test_no_trust_no_delete(self, m_delete):
        wf_ex = self._start(execution_trust=False)

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertNotIn('execution_trust_id', wf_ex.runtime_context)

        m_delete.assert_not_called()
