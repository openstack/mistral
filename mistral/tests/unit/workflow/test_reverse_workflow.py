# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

from mistral.db.sqlalchemy import models as m
from mistral.openstack.common import log as logging
from mistral.tests import base
from mistral.workbook import parser as spec_parser
from mistral.workflow import reverse_workflow as r_wf


LOG = logging.getLogger(__name__)


class ReverseWorkflowHandlerTest(base.BaseTest):
    def setUp(self):
        super(ReverseWorkflowHandlerTest, self).setUp()

        wf_spec = spec_parser.get_workbook_spec_from_yaml(
            base.get_resource('dsl_v2/reverse_workflow.yaml')
        )

        exec_db = m.WorkflowExecution()
        exec_db.update({
            'id': '1-2-3-4',
            'wf_spec': wf_spec.to_dict()
        })

        self.handler = r_wf.ReverseWorkflowHandler(exec_db)

    def test_start_workflow(self):
        # self.handler.start_workflow()

        # TODO(rakhmerov): Implement.
        pass

    def test_stop_workflow(self):
        # TODO(rakhmerov): Implement.
        pass

    def test_resume_workflow(self):
        # TODO(rakhmerov): Implement.
        pass

    def test_on_task_result_workflow(self):
        # TODO(rakhmerov): Implement.
        pass
