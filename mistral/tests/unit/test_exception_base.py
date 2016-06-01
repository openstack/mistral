# -*- encoding: utf-8 -*-
#
# Copyright 2014 Rackspace Hosting.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import six

from mistral import exceptions
from mistral.tests.unit import base


class ExceptionTestCase(base.BaseTest):
    """Test cases for exception code."""

    def test_nf_with_message(self):
        exc = exceptions.DBEntityNotFoundError('check_for_this')
        self.assertIn('check_for_this',
                      six.text_type(exc))
        self.assertEqual(404, exc.http_code)

    def test_nf_with_no_message(self):
        exc = exceptions.DBEntityNotFoundError()
        self.assertIn("Object not found",
                      six.text_type(exc))
        self.assertEqual(404, exc.http_code,)

    def test_duplicate_obj_code(self):
        exc = exceptions.DBDuplicateEntryError()
        self.assertIn("Database object already exists",
                      six.text_type(exc))
        self.assertEqual(409, exc.http_code,)

    def test_default_code(self):
        exc = exceptions.EngineException()
        self.assertEqual(500, exc.http_code)

    def test_default_message(self):
        exc = exceptions.EngineException()
        self.assertIn("An unknown exception occurred",
                      six.text_type(exc))
