# Copyright 2015 - Huawei Technologies Co. Ltd
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

from oslo_log import log as logging

from mistral.tests.unit.workbook.v2 import base as v2_base
from mistral import utils
from mistral.workbook.v2 import workflows


LOG = logging.getLogger(__name__)


class TaskSpecValidation(v2_base.WorkflowSpecValidationTestCase):
    def test_type_injection(self):
        tests = [
            ({'type': 'direct'}, False),
            ({'type': 'reverse'}, False)
        ]

        for wf_type, expect_error in tests:
            overlay = {'test': wf_type}
            wfs_spec = self._parse_dsl_spec(add_tasks=True,
                                            changes=overlay,
                                            expect_error=expect_error)

            if not expect_error:
                self.assertIsInstance(wfs_spec, workflows.WorkflowListSpec)
                self.assertEqual(1, len(wfs_spec.get_workflows()))

                wf_spec = wfs_spec.get_workflows()[0]

                self.assertEqual(wf_type['type'], wf_spec.get_type())

                for task in wf_spec.get_tasks():
                    self.assertEqual(task._data['type'], wf_type['type'])

    def test_action_or_workflow(self):
        tests = [
            ({'action': 'std.noop'}, False),
            ({'action': 'std.http url="openstack.org"'}, False),
            ({'action': 'std.http url="openstack.org" timeout=10'}, False),
            ({'action': 'std.http url=<% $.url %>'}, False),
            ({'action': 'std.http url=<% $.url %> timeout=<% $.t %>'}, False),
            ({'action': 'std.http url=<% * %>'}, True),
            ({'workflow': 'test.wf'}, False),
            ({'workflow': 'test.wf k1="v1"'}, False),
            ({'workflow': 'test.wf k1="v1" k2="v2"'}, False),
            ({'workflow': 'test.wf k1=<% $.v1 %>'}, False),
            ({'workflow': 'test.wf k1=<% $.v1 %> k2=<% $.v2 %>'}, False),
            ({'workflow': 'test.wf k1=<% * %>'}, True),
            ({'action': 'std.noop', 'workflow': 'test.wf'}, True),
            ({'action': 123}, True),
            ({'workflow': 123}, True),
            ({'action': ''}, True),
            ({'workflow': ''}, True),
            ({'action': None}, True),
            ({'workflow': None}, True)
        ]

        for task, expect_error in tests:
            overlay = {'test': {'tasks': {'task1': task}}}

            self._parse_dsl_spec(
                add_tasks=False,
                changes=overlay,
                expect_error=expect_error
            )

    def test_inputs(self):
        tests = [
            ({'input': ''}, True),
            ({'input': {}}, True),
            ({'input': None}, True),
            ({'input': {'k1': 'v1'}}, False),
            ({'input': {'k1': '<% $.v1 %>'}}, False),
            ({'input': {'k1': '<% 1 + 2 %>'}}, False),
            ({'input': {'k1': '<% * %>'}}, True)
        ]

        for task_input, expect_error in tests:
            overlay = {'test': {'tasks': {'task1': {'action': 'test.mock'}}}}

            utils.merge_dicts(overlay['test']['tasks']['task1'], task_input)

            self._parse_dsl_spec(
                add_tasks=False,
                changes=overlay,
                expect_error=expect_error
            )

    def test_with_items(self):
        tests = [
            ({'with-items': ''}, True),
            ({'with-items': []}, True),
            ({'with-items': ['']}, True),
            ({'with-items': None}, True),
            ({'with-items': 12345}, True),
            ({'with-items': 'x in y'}, True),
            ({'with-items': '<% $.y %>'}, True),
            ({'with-items': 'x in <% $.y %>'}, False),
            ({'with-items': ['x in [1, 2, 3]']}, False),
            ({'with-items': ['x in <% $.y %>']}, False),
            ({'with-items': ['x in <% $.y %>', 'i in [1, 2, 3]']}, False),
            ({'with-items': ['x in <% $.y %>', 'i in <% $.j %>']}, False),
            ({'with-items': ['x in <% * %>']}, True),
            ({'with-items': ['x in <% $.y %>', 'i in <% * %>']}, True)
        ]

        for with_item, expect_error in tests:
            overlay = {'test': {'tasks': {'get': with_item}}}

            self._parse_dsl_spec(
                add_tasks=True,
                changes=overlay,
                expect_error=expect_error
            )

    def test_publish(self):
        tests = [
            ({'publish': ''}, True),
            ({'publish': {}}, True),
            ({'publish': None}, True),
            ({'publish': {'k1': 'v1'}}, False),
            ({'publish': {'k1': '<% $.v1 %>'}}, False),
            ({'publish': {'k1': '<% 1 + 2 %>'}}, False),
            ({'publish': {'k1': '<% * %>'}}, True)
        ]

        for output, expect_error in tests:
            overlay = {'test': {'tasks': {'task1': {'action': 'test.mock'}}}}

            utils.merge_dicts(overlay['test']['tasks']['task1'], output)

            self._parse_dsl_spec(
                add_tasks=False,
                changes=overlay,
                expect_error=expect_error
            )

    def test_policies(self):
        tests = [
            ({'retry': {'count': 3, 'delay': 1}}, False),
            ({'retry': {
                'continue-on': '<% 1 %>', 'delay': 2,
                'break-on': '<% 1 %>', 'count': 2
            }}, False),
            ({'retry': {
                'count': 3, 'delay': 1, 'continue-on': '<% 1 %>'
            }}, False),
            ({'retry': {'count': '<% 3 %>', 'delay': 1}}, False),
            ({'retry': {'count': '<% * %>', 'delay': 1}}, True),
            ({'retry': {'count': 3, 'delay': '<% 1 %>'}}, False),
            ({'retry': {'count': 3, 'delay': '<% * %>'}}, True),
            ({'retry': {'count': -3, 'delay': 1}}, True),
            ({'retry': {'count': 3, 'delay': -1}}, True),
            ({'retry': {'count': '3', 'delay': 1}}, True),
            ({'retry': {'count': 3, 'delay': '1'}}, True),
            ({'retry': 'count=3 delay=1 break-on=<% false %>'}, False),
            ({'retry': 'count=3 delay=1'}, False),
            ({'retry': 'coun=3 delay=1'}, True),
            ({'retry': None}, True),
            ({'wait-before': 1}, False),
            ({'wait-before': '<% 1 %>'}, False),
            ({'wait-before': '<% * %>'}, True),
            ({'wait-before': -1}, True),
            ({'wait-before': 1.0}, True),
            ({'wait-before': '1'}, True),
            ({'wait-after': 1}, False),
            ({'wait-after': '<% 1 %>'}, False),
            ({'wait-after': '<% * %>'}, True),
            ({'wait-after': -1}, True),
            ({'wait-after': 1.0}, True),
            ({'wait-after': '1'}, True),
            ({'timeout': 300}, False),
            ({'timeout': '<% 300 %>'}, False),
            ({'timeout': '<% * %>'}, True),
            ({'timeout': -300}, True),
            ({'timeout': 300.0}, True),
            ({'timeout': '300'}, True),
            ({'pause-before': False}, False),
            ({'pause-before': '<% False %>'}, False),
            ({'pause-before': '<% * %>'}, True),
            ({'pause-before': 'False'}, True),
            ({'concurrency': 10}, False),
            ({'concurrency': '<% 10 %>'}, False),
            ({'concurrency': '<% * %>'}, True),
            ({'concurrency': -10}, True),
            ({'concurrency': 10.0}, True),
            ({'concurrency': '10'}, True)
        ]

        for policy, expect_error in tests:
            overlay = {'test': {'tasks': {'get': policy}}}

            self._parse_dsl_spec(
                add_tasks=True,
                changes=overlay,
                expect_error=expect_error
            )

    def test_direct_transition(self):
        tests = [
            ({'on-success': ['email']}, False),
            ({'on-success': [{'email': '<% 1 %>'}]}, False),
            ({'on-success': [{'email': '<% 1 %>'}, 'echo']}, False),
            ({'on-success': [{'email': '<% $.v1 in $.v2 %>'}]}, False),
            ({'on-success': [{'email': '<% * %>'}]}, True),
            ({'on-success': 'email'}, False),
            ({'on-success': None}, True),
            ({'on-success': ['']}, True),
            ({'on-success': []}, True),
            ({'on-success': ['email', 'email']}, True),
            ({'on-success': ['email', 12345]}, True),
            ({'on-error': ['email']}, False),
            ({'on-error': [{'email': '<% 1 %>'}]}, False),
            ({'on-error': [{'email': '<% 1 %>'}, 'echo']}, False),
            ({'on-error': [{'email': '<% $.v1 in $.v2 %>'}]}, False),
            ({'on-error': [{'email': '<% * %>'}]}, True),
            ({'on-error': 'email'}, False),
            ({'on-error': None}, True),
            ({'on-error': ['']}, True),
            ({'on-error': []}, True),
            ({'on-error': ['email', 'email']}, True),
            ({'on-error': ['email', 12345]}, True),
            ({'on-complete': ['email']}, False),
            ({'on-complete': [{'email': '<% 1 %>'}]}, False),
            ({'on-complete': [{'email': '<% 1 %>'}, 'echo']}, False),
            ({'on-complete': [{'email': '<% $.v1 in $.v2 %>'}]}, False),
            ({'on-complete': [{'email': '<% * %>'}]}, True),
            ({'on-complete': 'email'}, False),
            ({'on-complete': None}, True),
            ({'on-complete': ['']}, True),
            ({'on-complete': []}, True),
            ({'on-complete': ['email', 'email']}, True),
            ({'on-complete': ['email', 12345]}, True)
        ]

        for transition, expect_error in tests:
            overlay = {'test': {'tasks': {}}}

            utils.merge_dicts(overlay['test']['tasks'], {'get': transition})

            self._parse_dsl_spec(
                add_tasks=True,
                changes=overlay,
                expect_error=expect_error
            )

    def test_join(self):
        tests = [
            ({'join': ''}, True),
            ({'join': None}, True),
            ({'join': 'all'}, False),
            ({'join': 'one'}, False),
            ({'join': 0}, False),
            ({'join': 2}, False),
            ({'join': 3}, True),
            ({'join': '3'}, True),
            ({'join': -3}, True)
        ]

        on_success = {'on-success': ['email']}

        for join, expect_error in tests:
            overlay = {'test': {'tasks': {}}}

            utils.merge_dicts(overlay['test']['tasks'], {'get': on_success})
            utils.merge_dicts(overlay['test']['tasks'], {'echo': on_success})
            utils.merge_dicts(overlay['test']['tasks'], {'email': join})

            self._parse_dsl_spec(
                add_tasks=True,
                changes=overlay,
                expect_error=expect_error
            )

    def test_requires(self):
        tests = [
            ({'requires': ''}, True),
            ({'requires': []}, True),
            ({'requires': ['']}, True),
            ({'requires': None}, True),
            ({'requires': 12345}, True),
            ({'requires': ['echo']}, False),
            ({'requires': ['echo', 'get']}, False),
            ({'requires': 'echo'}, False),
        ]

        for require, expect_error in tests:
            overlay = {'test': {'tasks': {}}}

            utils.merge_dicts(overlay['test'], {'type': 'reverse'})
            utils.merge_dicts(overlay['test']['tasks'], {'email': require})

            self._parse_dsl_spec(
                add_tasks=True,
                changes=overlay,
                expect_error=expect_error
            )

    def test_keep_result(self):
        tests = [
            ({'keep-result': ''}, True),
            ({'keep-result': []}, True),
            ({'keep-result': 'asd'}, True),
            ({'keep-result': None}, True),
            ({'keep-result': 12345}, True),
            ({'keep-result': True}, False),
            ({'keep-result': False}, False),
            ({'keep-result': "<% 'a' in $.val %>"}, False),
            ({'keep-result': '<% 1 + 2 %>'}, False),
            ({'keep-result': '<% * %>'}, True)
        ]

        for keep_result, expect_error in tests:
            overlay = {'test': {'tasks': {}}}

            utils.merge_dicts(overlay['test']['tasks'], {'email': keep_result})

            self._parse_dsl_spec(
                add_tasks=True,
                changes=overlay,
                expect_error=expect_error
            )
