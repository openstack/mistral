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
    def run_check(self, code, checker, filename=None):
        pep8.register_check(checker)
        lines = textwrap.dedent(code).strip().splitlines(True)
        checker = pep8.Checker(filename=filename, lines=lines)
        with mock.patch('pep8.StandardReport.get_file_results'):
            checker.check_all()
        checker.report._deferred_print.sort()

        return checker.report._deferred_print

    def _assert_has_errors(self, code, checker, expected_errors=None,
                           filename=None):

        # Pull out the parts of the error that we'll match against.
        actual_errors = [e[:3] for e in
                         self.run_check(code, checker, filename)]
        self.assertEqual(expected_errors or [], actual_errors)

    def _assert_has_no_errors(self, code, checker, filename=None):
        self._assert_has_errors(code, checker, filename=filename)

    def test_no_assert_equal_true_false(self):
        code = """
                  self.assertEqual(context_is_admin, True)
                  self.assertEqual(context_is_admin, False)
                  self.assertEqual(True, context_is_admin)
                  self.assertEqual(False, context_is_admin)
                  self.assertNotEqual(context_is_admin, True)
                  self.assertNotEqual(context_is_admin, False)
                  self.assertNotEqual(True, context_is_admin)
                  self.assertNotEqual(False, context_is_admin)
               """
        errors = [(1, 0, 'M319'), (2, 0, 'M319'), (3, 0, 'M319'),
                  (4, 0, 'M319'), (5, 0, 'M319'), (6, 0, 'M319'),
                  (7, 0, 'M319'), (8, 0, 'M319')]
        self._assert_has_errors(code, checks.no_assert_equal_true_false,
                                expected_errors=errors)
        code = """
                  self.assertEqual(context_is_admin, stuff)
                  self.assertNotEqual(context_is_admin, stuff)
               """
        self._assert_has_no_errors(code, checks.no_assert_equal_true_false)

    def test_no_assert_true_false_is_not(self):
        code = """
                  self.assertTrue(test is None)
                  self.assertTrue(False is my_variable)
                  self.assertFalse(None is test)
                  self.assertFalse(my_variable is False)
               """
        errors = [(1, 0, 'M320'), (2, 0, 'M320'), (3, 0, 'M320'),
                  (4, 0, 'M320')]
        self._assert_has_errors(code, checks.no_assert_true_false_is_not,
                                expected_errors=errors)

    def test_check_python3_xrange(self):
        func = checks.check_python3_xrange
        self.assertEqual(1, len(list(func('for i in xrange(10)'))))
        self.assertEqual(1, len(list(func('for i in xrange    (10)'))))
        self.assertEqual(0, len(list(func('for i in range(10)'))))
        self.assertEqual(0, len(list(func('for i in six.moves.range(10)'))))

    def test_dict_iteritems(self):
        self.assertEqual(1, len(list(checks.check_python3_no_iteritems(
            "obj.iteritems()"))))

        self.assertEqual(0, len(list(checks.check_python3_no_iteritems(
            "six.iteritems(ob))"))))

    def test_dict_iterkeys(self):
        self.assertEqual(1, len(list(checks.check_python3_no_iterkeys(
            "obj.iterkeys()"))))

        self.assertEqual(0, len(list(checks.check_python3_no_iterkeys(
            "six.iterkeys(ob))"))))

    def test_dict_itervalues(self):
        self.assertEqual(1, len(list(checks.check_python3_no_itervalues(
            "obj.itervalues()"))))

        self.assertEqual(0, len(list(checks.check_python3_no_itervalues(
            "six.itervalues(ob))"))))


class TestLoggingWithWarn(BaseLoggingCheckTest):

    def test_using_deprecated_warn(self):
        data = self.code_ex.assert_not_using_deprecated_warn
        code = self.code_ex.shared_imports + data['code']
        errors = data['expected_errors']

        self._assert_has_errors(code, checks.CheckForLoggingIssues,
                                expected_errors=errors)
