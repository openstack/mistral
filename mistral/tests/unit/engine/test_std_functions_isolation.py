# Copyright 2026 - OVHcloud.
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

from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base

cfg.CONF.set_default('auth_enable', False, group='pecan')


WF = """---
version: '2.0'

wf:
  vars:
    gvar:
      k: v

  tasks:
    task1:
      action: std.noop
      publish:
        p1: v1
      on-success: task2

    task2:
      action: std.noop
      publish:
        a: "{{ execution().params.update({'hacked': 1}) }}"
        b: "{{ executions()[0].update({'description': 'hacked'}) }}"
        c: "{{ task('task1').published.update({'p1': 'hacked'}) }}"
        d: "{{ tasks()[0].spec.update({'hacked': 1}) }}"
        e: "{{ env().update({'hacked': 1}) }}"
        f: "{{ global('gvar').update({'k': 'hacked'}) }}"
        env_after: "{{ env() }}"
        global_after: "{{ global('gvar') }}"
"""


class StdFunctionsIsolationTest(base.EngineTestCase):
    def test_mutating_function_results_does_not_touch_db(self):
        self.override_config('immutable_sandbox', False, 'jinja')

        wf_service.create_workflows(WF)

        wf_ex = self.engine.start_workflow('wf', env={'k': 'v'})

        self.await_workflow_success(wf_ex.id)

        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            task1 = self._assert_single_item(
                wf_ex.task_executions,
                name='task1'
            )
            task2 = self._assert_single_item(
                wf_ex.task_executions,
                name='task2'
            )

            self.assertNotIn('hacked', wf_ex.params)
            self.assertNotEqual('hacked', wf_ex.description)
            self.assertEqual({'p1': 'v1'}, task1.published)
            self.assertNotIn('hacked', task1.spec)
            self.assertNotIn('hacked', task2.spec)
            self.assertEqual({'k': 'v'}, wf_ex.params['env'])
            self.assertEqual({'k': 'v'}, wf_ex.context['gvar'])
            self.assertEqual({'k': 'v'}, task2.published['env_after'])
            self.assertEqual({'k': 'v'}, task2.published['global_after'])
