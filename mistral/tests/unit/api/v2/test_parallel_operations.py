#  Copyright 2019 - Nokia Corporation
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import eventlet
from eventlet import semaphore
from unittest import mock

from mistral.api.controllers.v2 import execution
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.services import workflows as wf_service
from mistral.tests.unit.api import base
from mistral.tests.unit import base as unit_base
from mistral.tests.unit.engine import base as engine_base


WF_TEXT = """---
version: '2.0'

wf:
  tasks:
       task1:
         action: std.noop
"""


class TestParallelOperations(base.APITest, engine_base.EngineTestCase):
    def setUp(self):
        super(TestParallelOperations, self).setUp()

        wf_service.create_workflows(WF_TEXT)

        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        self.wf_ex_id = wf_ex.id

        self.decorator_call_cnt = 0
        self.threads = []
        self.addCleanup(self.kill_threads)

    def kill_threads(self):
        for thread in self.threads:
            thread.kill()

    def test_parallel_api_list_and_delete_operations(self):
        # One execution already exists. Let's create another one.
        wf_ex = self.engine.start_workflow('wf')

        self.await_workflow_success(wf_ex.id)

        self.assertEqual(2, len(db_api.get_workflow_executions()))

        delete_lock = semaphore.Semaphore(0)
        list_lock = semaphore.Semaphore(0)

        orig_func = execution._get_workflow_execution_resource

        def delete_():
            context.set_ctx(unit_base.get_context())

            db_api.delete_workflow_execution(self.wf_ex_id)

            # Unlocking the "list" operation.
            list_lock.release()

        def list_():
            resp = self.app.get('/v2/executions/')

            self.assertEqual(1, len(resp.json['executions']))

        # This decorator is needed to halt the thread of the "list"
        # operation and wait till the "delete" operation is over.
        # That way we'll reproduce the situation when the "list"
        # operation has already fetched the execution but it then
        # gets deleted before further lazy-loading of the execution
        # fields.
        def decorate_resource_function_(arg):
            self.decorator_call_cnt += 1

            # It makes sense to use this trick only once since only
            # one object gets deleted.
            if self.decorator_call_cnt == 1:
                # It's OK now to delete the execution so we release
                # the corresponding lock.
                delete_lock.release()

                # Wait till the "delete" operation has finished.
                list_lock.acquire()

            return orig_func(arg)

        with mock.patch.object(execution, '_get_workflow_execution_resource',
                               wraps=decorate_resource_function_):
            self.threads.append(eventlet.spawn(list_))

            # Make sure that the "list" operation came to the right point
            # which is just about the call to the resource function.
            delete_lock.acquire()

            self.threads.append(eventlet.spawn(delete_))

        for t in self.threads:
            t.wait()
