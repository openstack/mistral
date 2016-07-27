# Copyright 2015 - StackStorm, Inc.
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

from mistral.services import workflows as wf_service
from mistral.tests.unit import base
from mistral.workbook import parser as spec_parser


class SpecificationCachingTest(base.DbTestCase):
    def test_workflow_spec_caching(self):
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="Echo"
        """

        wfs = wf_service.create_workflows(wf_text)

        self.assertEqual(0, spec_parser.get_workflow_spec_cache_size())

        wf_spec = spec_parser.get_workflow_spec_by_id(wfs[0].id)

        self.assertIsNotNone(wf_spec)
        self.assertEqual(1, spec_parser.get_workflow_spec_cache_size())
