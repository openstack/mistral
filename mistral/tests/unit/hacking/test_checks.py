# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import textwrap

import mock
import pep8

from mistral.hacking import checks
from mistral.tests.unit import base
from mistral.tests.unit.mstrlfixtures import hacking as hacking_fixtures


class BaseLoggingCheckTest(base.BaseTest):

    def setUp(self):
        super(BaseLoggingCheckTest, self).setUp()
        self.code_ex = self.useFixture(self.get_fixture())

        self.addCleanup(delattr, self, 'code_ex')

    def get_checker(self):
        return checks.CheckForLoggingIssues

    def get_fixture(self):
        return hacking_fixtures.HackingLogging()

    # We are patching pep8 so that only the check under test is actually
    # installed.
    @mock.patch('pep8._checks',
                {'physical_line': {}, 'logical_line': {}, 'tree': {}})
    def run_check(self, code):
        pep8.register_check(self.get_checker())
        lines = textwrap.dedent(code).strip().splitlines(True)
        checker = pep8.Checker(lines=lines)
        checker.check_all()
        checker.report._deferred_print.sort()

        return checker.report._deferred_print

    def assert_has_errors(self, code, expected_errors=None):

        # Pull out the parts of the error that we'll match against.
        actual_errors = (e[:3] for e in self.run_check(code))

        # Adjust line numbers to make the fixture data more readable.
        import_lines = len(self.code_ex.shared_imports.split('\n')) - 1
        actual_errors = [(e[0] - import_lines, e[1], e[2])
                         for e in actual_errors]

        self.assertEqual(expected_errors or [], actual_errors)


class TestLoggingWithWarn(BaseLoggingCheckTest):

    def test_using_deprecated_warn(self):
        data = self.code_ex.assert_not_using_deprecated_warn
        code = self.code_ex.shared_imports + data['code']
        errors = data['expected_errors']

        self.assert_has_errors(code, expected_errors=errors)
