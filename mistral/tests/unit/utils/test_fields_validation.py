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

from wsme import exc as wsme_exc

from mistral.db.v2.sqlalchemy import models
from mistral.tests.unit import base
from mistral.utils import rest_utils


class FieldsListValidationTest(base.BaseTest):
    def test_unknown_field_raises_client_error(self):
        # An unknown 'fields' value must yield a 4xx client error, not an
        # unhandled AttributeError -> HTTP 500.
        self.assertRaises(
            wsme_exc.ClientSideError,
            rest_utils.fields_list_to_cls_fields_tuple,
            models.WorkflowExecution,
            ['does_not_exist']
        )

    def test_valid_fields_pass(self):
        result = rest_utils.fields_list_to_cls_fields_tuple(
            models.WorkflowExecution, ['id', 'name']
        )

        self.assertEqual(2, len(result))

    def test_empty_fields(self):
        self.assertEqual(
            (), rest_utils.fields_list_to_cls_fields_tuple(
                models.WorkflowExecution, None)
        )
