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

# NOTE(morganfainberg) This file shouldn't have flake8 run on it as it has
# code examples that will fail normal CI pep8/flake8 tests. This is expected.
# The code has been moved here to ensure that proper tests occur on the
# hacking/test_checks test cases.
# flake8: noqa

import fixtures


class HackingLogging(fixtures.Fixture):

    shared_imports = """
                import logging
                from oslo_log import log
                from oslo_log import log as logging
    """

    assert_not_using_deprecated_warn = {
        'code': """
                # Logger.warn has been deprecated in Python3 in favor of
                # Logger.warning
                LOG = log.getLogger(__name__)
                LOG.warn('text')
        """,
        'expected_errors': [
            (4, 9, 'M001'),
        ],
    }
