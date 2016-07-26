# Copyright 2016 - Brocade Communications Systems, Inc.
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

import mock
import uuid

from oslo_config import cfg
import osprofiler

from mistral import context
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import states


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')
cfg.CONF.set_default('enabled', True, group='profiler')
cfg.CONF.set_default('hmac_keys', 'foobar', group='profiler')
cfg.CONF.set_default('profiler_log_name', 'profile_trace', group='profiler')


class EngineProfilerTest(base.EngineTestCase):
    def setUp(self):
        super(EngineProfilerTest, self).setUp()

        # Configure the osprofiler.
        self.mock_profiler_log_func = mock.Mock(return_value=None)
        osprofiler.notifier.set(self.mock_profiler_log_func)

        self.ctx_serializer = context.RpcContextSerializer(
            context.JsonPayloadSerializer()
        )

    def test_profile_trace(self):
        wf_def = """
        version: '2.0'
        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Peace!"
        """

        wf_service.create_workflows(wf_def)

        ctx = {
            'trace_info': {
                'hmac_key': cfg.CONF.profiler.hmac_keys,
                'base_id': str(uuid.uuid4()),
                'parent_id': str(uuid.uuid4())
            }
        }

        self.ctx_serializer.deserialize_context(ctx)

        wf_ex = self.engine_client.start_workflow('wf', {})

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex['state'])

        self.await_workflow_success(wf_ex['id'])

        self.assertGreater(self.mock_profiler_log_func.call_count, 0)

    def test_no_profile_trace(self):
        wf_def = """
        version: '2.0'
        wf:
          type: direct
          tasks:
            task1:
              action: std.echo output="Peace!"
        """

        wf_service.create_workflows(wf_def)

        self.ctx_serializer.deserialize_context({})

        wf_ex = self.engine_client.start_workflow('wf', {})

        self.assertIsNotNone(wf_ex)
        self.assertEqual(states.RUNNING, wf_ex['state'])

        self.await_workflow_success(wf_ex['id'])

        self.assertEqual(self.mock_profiler_log_func.call_count, 0)
