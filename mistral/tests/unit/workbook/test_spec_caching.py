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

from mistral.db.v2 import api as db_api
from mistral.services import workbooks as wb_service
from mistral.services import workflows as wf_service
from mistral.tests.unit import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import states


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

        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(0, spec_parser.get_wf_definition_spec_cache_size())

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wfs[0].id,
            wfs[0].updated_at
        )

        self.assertIsNotNone(wf_spec)
        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(1, spec_parser.get_wf_definition_spec_cache_size())

    def test_workflow_spec_cache_update_via_workflow_service(self):
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="Echo"
        """

        wfs = wf_service.create_workflows(wf_text)

        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(0, spec_parser.get_wf_definition_spec_cache_size())

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wfs[0].id,
            wfs[0].updated_at
        )

        self.assertEqual(1, len(wf_spec.get_tasks()))
        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(1, spec_parser.get_wf_definition_spec_cache_size())

        # Now update workflow definition and check that cache is updated too.

        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="1"

            task2:
              action: std.echo output="2"
        """

        wfs = wf_service.update_workflows(wf_text)

        self.assertEqual(1, spec_parser.get_wf_definition_spec_cache_size())

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wfs[0].id,
            wfs[0].updated_at
        )

        self.assertEqual(2, len(wf_spec.get_tasks()))
        self.assertEqual(2, spec_parser.get_wf_definition_spec_cache_size())
        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())

    def test_workflow_spec_cache_update_via_workbook_service(self):
        wb_text = """
        version: '2.0'

        name: wb

        workflows:
          wf:
            tasks:
              task1:
                action: std.echo output="Echo"
        """

        wb_service.create_workbook_v2(wb_text)

        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(0, spec_parser.get_wf_definition_spec_cache_size())

        wf = db_api.get_workflow_definition('wb.wf')

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf.id,
            wf.updated_at
        )

        self.assertEqual(1, len(wf_spec.get_tasks()))
        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(1, spec_parser.get_wf_definition_spec_cache_size())

        # Now update workflow definition and check that cache is updated too.

        wb_text = """
        version: '2.0'

        name: wb

        workflows:
          wf:
            tasks:
              task1:
                action: std.echo output="1"

              task2:
                action: std.echo output="2"
        """

        wb_service.update_workbook_v2(wb_text)

        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(1, spec_parser.get_wf_definition_spec_cache_size())

        wf = db_api.get_workflow_definition(wf.id)

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf.id,
            wf.updated_at
        )

        self.assertEqual(2, len(wf_spec.get_tasks()))
        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(2, spec_parser.get_wf_definition_spec_cache_size())

    def test_cache_workflow_spec_by_execution_id(self):
        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="Echo"
        """

        wfs = wf_service.create_workflows(wf_text)

        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(0, spec_parser.get_wf_definition_spec_cache_size())

        wf_def = wfs[0]

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wf_def.id,
            wf_def.updated_at
        )

        self.assertEqual(1, len(wf_spec.get_tasks()))
        self.assertEqual(0, spec_parser.get_wf_execution_spec_cache_size())
        self.assertEqual(1, spec_parser.get_wf_definition_spec_cache_size())

        wf_ex = db_api.create_workflow_execution({
            'id': '1-2-3-4',
            'name': 'wf',
            'workflow_id': wf_def.id,
            'spec': wf_spec.to_dict(),
            'state': states.RUNNING
        })

        # Check that we can get a valid spec by execution id.

        wf_spec_by_exec_id = spec_parser.get_workflow_spec_by_execution_id(
            wf_ex.id
        )

        self.assertEqual(1, len(wf_spec_by_exec_id.get_tasks()))

        # Now update workflow definition and check that cache is updated too.

        wf_text = """
        version: '2.0'

        wf:
          tasks:
            task1:
              action: std.echo output="1"

            task2:
              action: std.echo output="2"
        """

        wfs = wf_service.update_workflows(wf_text)

        self.assertEqual(1, spec_parser.get_wf_definition_spec_cache_size())

        wf_spec = spec_parser.get_workflow_spec_by_definition_id(
            wfs[0].id,
            wfs[0].updated_at
        )

        self.assertEqual(2, len(wf_spec.get_tasks()))
        self.assertEqual(2, spec_parser.get_wf_definition_spec_cache_size())
        self.assertEqual(1, spec_parser.get_wf_execution_spec_cache_size())

        # Now finally update execution cache and check that we can
        # get a valid spec by execution id.
        spec_parser.cache_workflow_spec_by_execution_id(wf_ex.id, wf_spec)

        wf_spec_by_exec_id = spec_parser.get_workflow_spec_by_execution_id(
            wf_ex.id
        )

        self.assertEqual(2, len(wf_spec_by_exec_id.get_tasks()))
