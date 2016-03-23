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


from mistral.tests.unit import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import base as wf_base
from mistral.workflow import direct_workflow as direct_wf
from mistral.workflow import reverse_workflow as reverse_wf

from mistral.db.v2.sqlalchemy import models as db_models


DIRECT_WF = """
---
version: '2.0'

wf:
  type: direct

  tasks:
    task1:
      action: std.echo output="Hey"
"""

REVERSE_WF = """
---
version: '2.0'

wf:
  type: reverse

  tasks:
    task1:
      action: std.echo output="Hey"
"""


class WorkflowControllerTest(base.BaseTest):
    def test_get_controller_direct(self):
        wf_spec = spec_parser.get_workflow_list_spec_from_yaml(DIRECT_WF)[0]
        wf_ex = db_models.WorkflowExecution(spec=wf_spec.to_dict())

        self.assertIsInstance(
            wf_base.get_controller(wf_ex, wf_spec),
            direct_wf.DirectWorkflowController
        )

    def test_get_controller_reverse(self):
        wf_spec = spec_parser.get_workflow_list_spec_from_yaml(REVERSE_WF)[0]
        wf_ex = db_models.WorkflowExecution(spec=wf_spec.to_dict())

        self.assertIsInstance(
            wf_base.get_controller(wf_ex, wf_spec),
            reverse_wf.ReverseWorkflowController
        )
