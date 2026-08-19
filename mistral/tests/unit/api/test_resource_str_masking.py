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

from mistral.api.controllers.v2 import resources
from mistral.tests.unit import base

SECRET = 'SUPER_SECRET_VALUE'


class ResourceStrMaskingTest(base.BaseTest):
    """str(resource) must never expose secret-bearing attributes.

    Controllers routinely log resources (``LOG.info("... %s", resource)``);
    the workflow input/output/params/env/result/published fields can hold
    client-supplied secrets, so __str__ masks them.
    """

    def test_execution_masks_input_and_params(self):
        wf_ex = resources.Execution()
        wf_ex.id = 'the-id'
        wf_ex.workflow_name = 'wf'
        wf_ex.input = {'password': SECRET}
        wf_ex.params = {'env': {'token': SECRET}}

        s = str(wf_ex)

        self.assertNotIn(SECRET, s)
        self.assertIn("input='***'", s)
        self.assertIn("params='***'", s)
        # Non-sensitive fields stay visible.
        self.assertIn("workflow_name='wf'", s)
        self.assertIn("id='the-id'", s)

    def test_unset_sensitive_attr_is_not_masked(self):
        # An unset field stays readable (not turned into '***').
        wf_ex = resources.Execution()
        wf_ex.id = 'the-id'

        self.assertNotIn("input='***'", str(wf_ex))

    def test_task_masks_result_and_published(self):
        task = resources.Task()
        task.id = 't-id'
        task.name = 'task1'
        task.result = SECRET
        task.published = {'x': SECRET}

        s = str(task)

        self.assertNotIn(SECRET, s)
        self.assertIn("result='***'", s)
        self.assertIn("published='***'", s)
