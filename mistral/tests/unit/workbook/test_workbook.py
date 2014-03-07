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

import pkg_resources as pkg
import unittest2

from mistral.engine.actions import action_types as a_t
from mistral import dsl_parser as parser
from mistral import version


class DSLModelTest(unittest2.TestCase):
    def setUp(self):
        self.doc = open(pkg.resource_filename(
            version.version_info.package,
            "tests/resources/test_rest.yaml")).read()

    def test_load_dsl(self):
        self.workbook = parser.get_workbook(self.doc)
        self.assertEqual(self.workbook.workflow.tasks.items,
                         self.workbook.tasks.items)
        self.assertEqual(self.workbook.tasks.get("create-vms").name,
                         "create-vms")
        self.assertEqual(self.workbook.services.get("MyRest").type,
                         "MISTRAL_REST_API")

    def test_tasks(self):
        self.workbook = parser.get_workbook(self.doc)
        self.assertEqual(len(self.workbook.tasks), 6)
        attach_volumes = self.workbook.tasks.get("attach-volumes")
        self.assertEqual(attach_volumes.get_action_service(), "MyRest")
        t_parameters = {"image_id": 1234, "flavor_id": 2}
        create_vm_nova = self.workbook.tasks.get("create-vm-nova")
        self.assertEqual(create_vm_nova.parameters, t_parameters)
        attach_requires = {"create-vms": ''}
        self.assertEqual(attach_volumes.requires, attach_requires)
        subsequent = self.workbook.tasks.get("test_subsequent")
        subseq_success = subsequent.get_on_success()
        subseq_error = subsequent.get_on_error()
        subseq_finish = subsequent.get_on_finish()
        self.assertEqual(subseq_success, {"attach-volumes": ''})
        self.assertEqual(subseq_error, {"backup-vms": "$.status != 'OK'",
                                        "attach-volumes": ''})
        self.assertEqual(subseq_finish, {"create-vms": ''})

    def test_actions(self):
        self.workbook = parser.get_workbook(self.doc)
        actions = self.workbook.services.get("MyRest").actions
        self.assertEqual(len(actions), 4)
        create_vm = actions.get("create-vm")
        self.assertIn('method', create_vm.parameters)

    def test_services(self):
        self.workbook = parser.get_workbook(self.doc)
        services = self.workbook.services
        self.assertEqual(len(services), 2)
        nova_service = services.get("Nova")
        self.assertEqual(nova_service.type, a_t.REST_API)
        self.assertIn("baseUrl", nova_service.parameters)

    def test_triggers(self):
        self.workbook = parser.get_workbook(self.doc)
        triggers = self.workbook.get_triggers()
        self.assertEqual(len(triggers), 1)
