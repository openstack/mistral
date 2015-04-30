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
import mock
from oslo.config import cfg

from mistral.services import security
from mistral.services import triggers as t_s
from mistral.services import workflows
from mistral.tests import base

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


class TriggerServiceV2Test(base.DbTestCase):
    def setUp(self):
        super(TriggerServiceV2Test, self).setUp()

        self.wf = workflows.create_workflows(WORKFLOW_LIST)[0]

    def test_trigger_create(self):
        trigger = t_s.create_cron_trigger(
            'test',
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

    def test_oneshot_trigger_create(self):
        trigger = t_s.create_cron_trigger(
            'test',
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
            'test',
            self.wf.name,
            {},
            {},
            '*/2 * * * *',
            None,
            None,
            datetime.datetime(2010, 8, 25)
        )

        self.assertEqual('my_trust_id', trigger.trust_id)

    def test_get_trigger_in_correct_orders(self):
        t_s.create_cron_trigger(
            'test1',
            self.wf.name,
            {},
            {},
            '*/5 * * * *',
            None,
            None,
            datetime.datetime(2010, 8, 25)
        )

        t_s.create_cron_trigger(
            'test2',
            self.wf.name,
            {},
            {},
            '*/1 * * * *',
            None,
            None,
            datetime.datetime(2010, 8, 22)
        )

        t_s.create_cron_trigger(
            'test3',
            self.wf.name,
            {},
            {},
            '*/2 * * * *',
            None,
            None,
            datetime.datetime(2010, 9, 21)
        )

        t_s.create_cron_trigger(
            'test4',
            self.wf.name,
            {},
            {},
            '*/3 * * * *',
            None,
            None,
            datetime.datetime.now() + datetime.timedelta(0, 50)
        )

        trigger_names = [t.name for t in t_s.get_next_cron_triggers()]

        self.assertEqual(trigger_names, ['test2', 'test1', 'test3'])
