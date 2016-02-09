# Copyright 2015 - Huawei Technologies Co. Ltd
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

import mock

from mistral import exceptions
from mistral.tests.unit import base
from mistral.workflow import base as wf_base
from mistral.workflow import direct_workflow
from mistral.workflow import reverse_workflow


class WorkflowControllerTest(base.BaseTest):
    def test_get_class_direct(self):
        wf_handler_cls = wf_base.WorkflowController._get_class("direct")

        self.assertIs(wf_handler_cls, direct_workflow.DirectWorkflowController)

    def test_get_class_reverse(self):
        wf_handler_cls = wf_base.WorkflowController._get_class("reverse")

        self.assertIs(wf_handler_cls,
                      reverse_workflow.ReverseWorkflowController)

    def test_get_class_notfound(self):
        exc = self.assertRaises(
            exceptions.NotFoundException,
            wf_base.WorkflowController._get_class,
            "invalid"
        )

        self.assertIn("Failed to find a workflow controller", str(exc))

    @mock.patch("mistral.workbook.parser.get_workflow_spec")
    @mock.patch("mistral.workflow.base.WorkflowController._get_class")
    def test_get_handler(self, mock_get_class, mock_get_spec):
        mock_wf_spec = mock.MagicMock()
        mock_wf_spec.get_type.return_value = "direct"
        mock_get_spec.return_value = mock_wf_spec
        mock_handler_cls = mock.MagicMock()
        mock_get_class.return_value = mock_handler_cls
        wf_ex = {"spec": "spec"}

        wf_base.WorkflowController.get_controller(wf_ex)

        mock_get_spec.assert_called_once_with("spec")
        mock_get_class.assert_called_once_with("direct")
        mock_handler_cls.assert_called_once_with(wf_ex, mock_wf_spec)
