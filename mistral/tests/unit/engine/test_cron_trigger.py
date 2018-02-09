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
import datetime

import mock
from oslo_config import cfg

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import periodic
from mistral.services import security
from mistral.services import triggers
from mistral.services import workflows
from mistral.tests.unit.engine import base
from mistral import utils


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
    @mock.patch.object(security,
                       'create_trust',
                       type('trust', (object,), {'id': 'my_trust_id'}))
    @mock.patch('mistral.rpc.clients.get_engine_client')
    def test_start_workflow(self, get_engine_client_mock):
        cfg.CONF.set_default('auth_enable', True, group='pecan')

        wf = workflows.create_workflows(WORKFLOW_LIST)[0]

        t = triggers.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
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

        next_trigger = triggers.get_next_cron_triggers()[0]
        next_execution_time_before = next_trigger.next_execution_time

        periodic.process_cron_triggers_v2(None, None)

        start_wf_mock = get_engine_client_mock.return_value.start_workflow

        start_wf_mock.assert_called_once()

        # Check actual parameters of the call.
        self.assertEqual(
            ('my_wf', '', None, {}),
            start_wf_mock.mock_calls[0][1]
        )
        self.assertIn(
            t.id,
            start_wf_mock.mock_calls[0][2]['description']
        )

        next_triggers = triggers.get_next_cron_triggers()

        self.assertEqual(1, len(next_triggers))

        next_trigger = next_triggers[0]
        next_execution_time_after = next_trigger.next_execution_time

        # Checking the workflow was executed, by
        # verifying that the next execution time changed.
        self.assertNotEqual(
            next_execution_time_before,
            next_execution_time_after
        )

    def test_workflow_without_auth(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')

        wf = workflows.create_workflows(WORKFLOW_LIST)[0]

        triggers.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            wf.name,
            {},
            {},
            '* * * * * */1',
            None,
            None,
            None
        )

        next_triggers = triggers.get_next_cron_triggers()

        self.assertEqual(1, len(next_triggers))

        next_trigger = next_triggers[0]
        next_execution_time_before = next_trigger.next_execution_time

        periodic.process_cron_triggers_v2(None, None)

        next_triggers = triggers.get_next_cron_triggers()

        self.assertEqual(1, len(next_triggers))

        next_trigger = next_triggers[0]
        next_execution_time_after = next_trigger.next_execution_time

        self.assertNotEqual(
            next_execution_time_before,
            next_execution_time_after
        )

    @mock.patch('mistral.services.triggers.validate_cron_trigger_input')
    def test_create_cron_trigger_with_pattern_and_first_time(self,
                                                             validate_mock):
        cfg.CONF.set_default('auth_enable', False, group='pecan')

        wf = workflows.create_workflows(WORKFLOW_LIST)[0]

        # Make the first_time 1 sec later than current time, in order to make
        # it executed by next cron-trigger task.
        first_time = datetime.datetime.utcnow() + datetime.timedelta(0, 1)

        # Creates a cron-trigger with pattern and first time, ensure the
        # cron-trigger can be executed more than once, and cron-trigger will
        # not be deleted.
        trigger_name = 'trigger-%s' % utils.generate_unicode_uuid()

        cron_trigger = triggers.create_cron_trigger(
            trigger_name,
            wf.name,
            {},
            {},
            '*/1 * * * *',
            first_time,
            None,
            None
        )

        self.assertEqual(
            first_time,
            cron_trigger.next_execution_time
        )

        periodic.process_cron_triggers_v2(None, None)

        # After process_triggers context is set to None, need to reset it.
        auth_ctx.set_ctx(self.ctx)

        next_time = triggers.get_next_execution_time(
            cron_trigger.pattern,
            cron_trigger.next_execution_time
        )

        cron_trigger_db = db_api.get_cron_trigger(trigger_name)

        self.assertIsNotNone(cron_trigger_db)
        self.assertEqual(
            next_time,
            cron_trigger_db.next_execution_time
        )

    def test_validate_cron_trigger_input_first_time(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')

        first_time = datetime.datetime.utcnow() + datetime.timedelta(0, 1)

        self.assertRaises(
            exc.InvalidModelException,
            triggers.validate_cron_trigger_input,
            None,
            first_time,
            None
        )
