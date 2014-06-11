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

from mistral import dsl_parser as parser
from mistral.tests import base


SIMPLE_WORKBOOK = """
Workflow:
  tasks:
    create-vms:
      action: MyRest.create-vm
"""


class DSLModelTest(base.BaseTest):
    def setUp(self):
        super(DSLModelTest, self).setUp()
        self.doc = base.get_resource("test_rest.yaml")

    def test_load_dsl(self):
        wb = parser.get_workbook(self.doc)

        self.assertEqual(wb.workflow.tasks.items, wb.tasks.items)
        self.assertEqual(wb.tasks.get("create-vms").name, "create-vms")
        self.assertEqual(4, len(wb.namespaces.get("MyRest").actions))

    def test_tasks(self):
        wb = parser.get_workbook(self.doc)
        self.assertEqual(len(wb.tasks), 6)

        attach_volumes = wb.tasks.get("attach-volumes")

        self.assertEqual(attach_volumes.get_action_namespace(), "MyRest")

        t_parameters = {"image_id": 1234, "flavor_id": 2}
        create_vm_nova = wb.tasks.get("create-vm-nova")

        self.assertEqual(create_vm_nova.parameters, t_parameters)

        attach_requires = {"create-vms": ''}

        self.assertEqual(attach_volumes.requires, attach_requires)

        subsequent = wb.tasks.get("test_subsequent")

        subseq_success = subsequent.get_on_success()
        subseq_error = subsequent.get_on_error()
        subseq_finish = subsequent.get_on_finish()

        self.assertEqual(subseq_success, {"attach-volumes": ''})
        self.assertEqual(subseq_error, {"backup-vms": "$.status != 'OK'",
                                        "attach-volumes": ''})
        self.assertEqual(subseq_finish, {"create-vms": ''})

    def test_actions(self):
        wb = parser.get_workbook(self.doc)

        actions = wb.namespaces.get("MyRest").actions

        self.assertEqual(len(actions), 4)

        create_vm = actions.get("create-vm")

        base_params = create_vm.base_parameters

        self.assertEqual('std.mistral_http', create_vm.clazz)
        self.assertIn('method', base_params)
        self.assertIn('headers', base_params)
        self.assertEqual('$.auth_token',
                         base_params['headers']['X-Auth-Token'])
        self.assertEqual('application/json',
                         base_params['headers']['Content-Type'])

        action = wb.get_action("MyRest.create-vm")

        self.assertIsNotNone(action)
        self.assertEqual("create-vm", action.name)
        self.assertEqual("MyRest", action.namespace)

    def test_namespaces(self):
        wb = parser.get_workbook(self.doc)

        self.assertEqual(len(wb.namespaces), 2)

        nova_namespace = wb.namespaces.get("Nova")

        self.assertEqual(1, len(nova_namespace.actions))

    def test_workbook_without_namespaces(self):
        parser.get_workbook(SIMPLE_WORKBOOK)

    def test_triggers(self):
        wb = parser.get_workbook(self.doc)

        self.assertEqual(len(wb.get_triggers()), 1)
