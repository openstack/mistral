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

import datetime
import time
from unittest import mock

from oslo_config import cfg
from oslo_utils import timeutils

from mistral import exceptions as exc
from mistral.rpc import clients as rpc
from mistral.services import periodic
from mistral.services import security
from mistral.services import triggers as t_s
from mistral.services import workflows
from mistral.tests.unit import base
from mistral_lib import utils

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


WORKFLOW_LIST = """
---
version: '2.0'

my_wf:
  type: direct

  tasks:
    task1:
      action: std.echo output='Hi!'
"""

advance_cron_trigger_orig = periodic.advance_cron_trigger


def new_advance_cron_trigger(ct):
    """Wrap the original advance_cron_trigger method.

    This method makes sure that the other coroutines will also run
    while this thread is executing. Without explicitly passing control to
    another coroutine the process_cron_triggers_v2 will finish looping
    over all the cron triggers in one coroutine without any sharing at all.
    """
    time.sleep()
    modified = advance_cron_trigger_orig(ct)
    time.sleep()

    return modified


class TriggerServiceV2Test(base.DbTestCase):
    def setUp(self):
        super(TriggerServiceV2Test, self).setUp()

        self.wf = workflows.create_workflows(WORKFLOW_LIST)[0]

    def test_trigger_create(self):
        trigger = t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            '*/5 * * * *',
            None,
            None,
            datetime.datetime(2010, 8, 25)
        )

        self.assertEqual(
            datetime.datetime(2010, 8, 25, 0, 5),
            trigger.next_execution_time
        )

        next_time = t_s.get_next_execution_time(
            trigger['pattern'],
            trigger.next_execution_time
        )

        self.assertEqual(datetime.datetime(2010, 8, 25, 0, 10), next_time)

    def test_trigger_create_with_wf_id(self):
        trigger = t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            None,
            {},
            {},
            '*/5 * * * *',
            None,
            None,
            datetime.datetime(2010, 8, 25),
            workflow_id=self.wf.id
        )

        self.assertEqual(self.wf.name, trigger.workflow_name)

    def test_trigger_create_the_same_first_time_or_count(self):
        t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            '*/5 * * * *',
            "4242-12-25 13:37",
            2,
            datetime.datetime(2010, 8, 25)
        )

        t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            '*/5 * * * *',
            "4242-12-25 13:37",
            4,
            datetime.datetime(2010, 8, 25)
        )

        t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            '*/5 * * * *',
            "5353-12-25 13:37",
            2,
            datetime.datetime(2010, 8, 25)
        )

        # Creations above should be ok.

        # But creation with the same count and first time
        # simultaneously leads to error.
        self.assertRaises(
            exc.DBDuplicateEntryError,
            t_s.create_cron_trigger,
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            '*/5 * * * *',
            "4242-12-25 13:37",
            2,
            None
        )

    def test_trigger_create_wrong_workflow_input(self):
        wf_with_input = """---
        version: '2.0'

        some_wf:
          input:
            - some_var
          tasks:
            some_task:
              action: std.echo output=<% $.some_var %>
        """
        workflows.create_workflows(wf_with_input)
        exception = self.assertRaises(
            exc.InputException,
            t_s.create_cron_trigger,
            'trigger-%s' % utils.generate_unicode_uuid(),
            'some_wf',
            {},
            {},
            '*/5 * * * *',
            None,
            None,
            datetime.datetime(2010, 8, 25)
        )

        self.assertIn('Invalid input', str(exception))
        self.assertIn('some_wf', str(exception))

    def test_oneshot_trigger_create(self):
        trigger = t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            None,
            "4242-12-25 13:37",
            None,
            datetime.datetime(2010, 8, 25)
        )

        self.assertEqual(
            datetime.datetime(4242, 12, 25, 13, 37),
            trigger.next_execution_time
        )

    @mock.patch.object(security, 'create_trust',
                       type('trust', (object,), {'id': 'my_trust_id'}))
    def test_create_trust_in_trigger(self):
        cfg.CONF.set_default('auth_enable', True, group='pecan')
        self.addCleanup(
            cfg.CONF.set_default, 'auth_enable',
            False, group='pecan'
        )

        trigger = t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            '*/2 * * * *',
            None,
            None,
            datetime.datetime(2010, 8, 25)
        )

        self.assertEqual('my_trust_id', trigger.trust_id)

    @mock.patch.object(security, 'create_trust',
                       type('trust', (object,), {'id': 'my_trust_id'}))
    @mock.patch.object(security, 'create_context')
    @mock.patch.object(rpc.EngineClient, 'start_workflow', mock.Mock())
    @mock.patch(
        'mistral.services.periodic.advance_cron_trigger',
        mock.MagicMock(side_effect=new_advance_cron_trigger)
    )
    @mock.patch.object(security, 'delete_trust')
    def test_create_delete_trust_in_trigger(self, delete_trust, create_ctx):
        create_ctx.return_value = self.ctx
        cfg.CONF.set_default('auth_enable', True, group='pecan')
        trigger_thread = periodic.setup()
        self.addCleanup(trigger_thread.stop)
        self.addCleanup(
            cfg.CONF.set_default, 'auth_enable',
            False, group='pecan'
        )

        t_s.create_cron_trigger(
            'trigger-%s' % utils.generate_unicode_uuid(),
            self.wf.name,
            {},
            {},
            '* * * * * *',
            None,
            1,
            datetime.datetime(2010, 8, 25)
        )

        time.sleep(1)
        self.assertEqual(0, delete_trust.call_count)

    def test_get_trigger_in_correct_orders(self):
        t1_name = 'trigger-%s' % utils.generate_unicode_uuid()

        t_s.create_cron_trigger(
            t1_name,
            self.wf.name,
            {},
            pattern='*/5 * * * *',
            start_time=datetime.datetime(2010, 8, 25)
        )

        t2_name = 'trigger-%s' % utils.generate_unicode_uuid()

        t_s.create_cron_trigger(
            t2_name,
            self.wf.name,
            {},
            pattern='*/1 * * * *',
            start_time=datetime.datetime(2010, 8, 22)
        )

        t3_name = 'trigger-%s' % utils.generate_unicode_uuid()

        t_s.create_cron_trigger(
            t3_name,
            self.wf.name,
            {},
            pattern='*/2 * * * *',
            start_time=datetime.datetime(2010, 9, 21)
        )

        t4_name = 'trigger-%s' % utils.generate_unicode_uuid()

        t_s.create_cron_trigger(
            t4_name,
            self.wf.name,
            {},
            pattern='*/3 * * * *',
            start_time=timeutils.utcnow() + datetime.timedelta(0, 50)
        )

        trigger_names = [t.name for t in t_s.get_next_cron_triggers()]

        self.assertEqual([t2_name, t1_name, t3_name], trigger_names)

    @mock.patch(
        'mistral.services.periodic.advance_cron_trigger',
        mock.MagicMock(side_effect=new_advance_cron_trigger)
    )
    @mock.patch.object(rpc.EngineClient, 'start_workflow')
    def test_single_execution_with_multiple_processes(self, start_wf_mock):
        def stop_thread_groups():
            print('Killing cron trigger threads...')
            [tg.stop() for tg in self.trigger_threads]

        self.trigger_threads = [
            periodic.setup(),
            periodic.setup(),
            periodic.setup()
        ]
        self.addCleanup(stop_thread_groups)

        trigger_count = 5
        t_s.create_cron_trigger(
            'ct1',
            self.wf.name,
            {},
            {},
            '* * * * * */1',  # Every second
            None,
            trigger_count,
            datetime.datetime(2010, 8, 25)
        )

        # Wait until there are 'trigger_count' executions.
        self._await(
            lambda: self._wait_for_single_execution_with_multiple_processes(
                trigger_count,
                start_wf_mock
            )
        )

        # Wait some more and make sure there are no more than 'trigger_count'
        # executions.
        time.sleep(5)

        self.assertEqual(trigger_count, start_wf_mock.call_count)

    def _wait_for_single_execution_with_multiple_processes(self, trigger_count,
                                                           start_wf_mock):
        time.sleep(1)

        return trigger_count == start_wf_mock.call_count

    def test_get_next_execution_time(self):
        pattern = '*/20 * * * *'
        start_time = datetime.datetime(2016, 3, 22, 23, 40)
        result = t_s.get_next_execution_time(pattern, start_time)
        self.assertEqual(result, datetime.datetime(2016, 3, 23, 0, 0))
