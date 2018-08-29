# Copyright 2017 - Nokia Networks.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import mock

import cachetools
from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import actions as action_service
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from mistral.workflow import lookup_utils
from mistral.workflow import states

# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class LookupUtilsTest(base.EngineTestCase):
    def test_task_execution_cache_invalidation(self):
        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.noop
              on-success: join_task

            task2:
              action: std.noop
              on-success: join_task

            join_task:
              join: all
              on-success: task4

            task4:
              action: std.noop
              pause-before: true
        """

        wf_service.create_workflows(wf_text)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_paused(wf_ex.id)

        with db_api.transaction():
            # Note: We need to reread execution to access related tasks.
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            tasks = wf_ex.task_executions

        self.assertEqual(4, len(tasks))

        self._assert_single_item(tasks, name='task1', state=states.SUCCESS)
        self._assert_single_item(tasks, name='task2', state=states.SUCCESS)
        self._assert_single_item(tasks, name='join_task', state=states.SUCCESS)
        self._assert_single_item(tasks, name='task4', state=states.IDLE)

        # Expecting one cache entry because we know that 'join' operation
        # uses cached lookups and the workflow is not finished yet.
        self.assertEqual(1, lookup_utils.get_task_execution_cache_size())

        self.engine.resume_workflow(wf_ex.id)

        self.await_workflow_success(wf_ex.id)

        # Expecting that the cache size is 0 because the workflow has
        # finished and invalidated corresponding cache entry.
        self.assertEqual(0, lookup_utils.get_task_execution_cache_size())

    def test_action_definition_cache_ttl(self):
        action = """---
        version: '2.0'

        action1:
          base: std.echo output='Hi'
          output:
            result: $
        """

        wf_text = """---
        version: '2.0'

        wf:
          tasks:
            task1:
              action: action1
              on-success: join_task

            task2:
              action: action1
              on-success: join_task

            join_task:
              join: all
              on-success: task4

            task4:
              action: action1
              pause-before: true
        """

        wf_service.create_workflows(wf_text)

        # Create an action.
        db_actions = action_service.create_actions(action)

        self.assertEqual(1, len(db_actions))
        self._assert_single_item(db_actions, name='action1')

        # Explicitly mark the action to be deleted after the test execution.
        self.addCleanup(db_api.delete_action_definitions, name='action1')

        # Reinitialise the cache with reduced action_definition_cache_time
        # to make the test faster.
        new_cache = cachetools.TTLCache(
            maxsize=1000,
            ttl=5  # 5 seconds
        )
        cache_patch = mock.patch.object(
            lookup_utils, '_ACTION_DEF_CACHE', new_cache)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)

        # Start workflow.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_paused(wf_ex.id)

        # Check that 'action1' 'echo' and 'noop' are cached.
        self.assertEqual(3, lookup_utils.get_action_definition_cache_size())
        self.assertIn('action1', lookup_utils._ACTION_DEF_CACHE)
        self.assertIn('std.noop', lookup_utils._ACTION_DEF_CACHE)
        self.assertIn('std.echo', lookup_utils._ACTION_DEF_CACHE)

        # Wait some time until cache expires
        self._await(
            lambda: lookup_utils.get_action_definition_cache_size() == 0,
            fail_message="No triggers were found"
        )

        self.assertEqual(0, lookup_utils.get_action_definition_cache_size())

        self.engine.resume_workflow(wf_ex.id)

        self.await_workflow_success(wf_ex.id)

        # Check all actions are cached again.
        self.assertEqual(2, lookup_utils.get_action_definition_cache_size())
        self.assertIn('action1', lookup_utils._ACTION_DEF_CACHE)
        self.assertIn('std.echo', lookup_utils._ACTION_DEF_CACHE)
