# Copyright 2015 Alcatel-Lucent, Inc.
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

import mock
from oslo_config import cfg
from oslo_log import log as logging

from mistral.services import periodic
from mistral.services import security
from mistral.services import triggers as t_s
from mistral.services import workflows
from mistral.tests.unit.engine import base

LOG = logging.getLogger(__name__)

WORKFLOW_LIST = """
---
version: '2.0'

my_wf:
  type: direct

  tasks:
    task1:
      action: std.echo output='Hi!'
"""


class ProcessCronTriggerTest(base.EngineTestCase):

    @mock.patch.object(security, 'create_trust',
                       type('trust', (object,), {'id': 'my_trust_id'}))
    def test_start_workflow(self):
        cfg.CONF.set_default('auth_enable', True, group='pecan')
        wf = workflows.create_workflows(WORKFLOW_LIST)[0]
        t = t_s.create_cron_trigger(
            'test',
            wf.name,
            {},
            {},
            '* * * * * */1',
            None,
            None,
            None
        )

        self.assertEqual('my_trust_id', t.trust_id)

        cfg.CONF.set_default('auth_enable', False, group='pecan')
        m_p_t = periodic.MistralPeriodicTasks(cfg.CONF)
        next_cron_trigger = t_s.get_next_cron_triggers()[0]
        next_execution_before = next_cron_trigger.next_execution_time

        m_p_t.process_cron_triggers_v2(None)

        next_cron_trigger = t_s.get_next_cron_triggers()[0]
        next_execution_after = next_cron_trigger.next_execution_time

        # Checking the workflow was executed, by
        # verifying that the next execution time changed.
        self.assertNotEqual(next_execution_before, next_execution_after)
