# Copyright 2018 - Extreme Networks, Inc.
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

from oslo_log import log as logging

from mistral.tests.unit.engine import base as engine_test_base


LOG = logging.getLogger(__name__)


class NotifierTestCase(engine_test_base.EngineTestCase):

    def await_workflow_success(self, wf_ex_id, post_delay=1):
        # Override the original wait method to add a delay to allow enough
        # time for the notification events to get processed.
        super(NotifierTestCase, self).await_workflow_success(wf_ex_id)
        self._sleep(post_delay)

    def await_workflow_error(self, wf_ex_id, post_delay=1):
        # Override the original wait method to add a delay to allow enough
        # time for the notification events to get processed.
        super(NotifierTestCase, self).await_workflow_error(wf_ex_id)
        self._sleep(post_delay)

    def await_workflow_paused(self, wf_ex_id, post_delay=1):
        # Override the original wait method to add a delay to allow enough
        # time for the notification events to get processed.
        super(NotifierTestCase, self).await_workflow_paused(wf_ex_id)
        self._sleep(post_delay)

    def await_workflow_cancelled(self, wf_ex_id, post_delay=1):
        # Override the original wait method to add a delay to allow enough
        # time for the notification events to get processed.
        super(NotifierTestCase, self).await_workflow_cancelled(wf_ex_id)
        self._sleep(post_delay)
