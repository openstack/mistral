# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pkg_resources as pkg
import unittest2

from mistral import dsl
from mistral import version


class DSLParserTest(unittest2.TestCase):
    def setUp(self):
        doc = open(pkg.resource_filename(
            version.version_info.package,
            "tests/resources/test_rest.yaml")).read()
        self.dsl = dsl.Parser(doc)

    def test_services(self):
        service = self.dsl.get_service("MyRest")
        self.assertEqual(service["type"], "REST_API")
        self.assertIn("baseUrl", service["parameters"])
        services = self.dsl.get_services()
        self.assertEqual(len(services), 1)
        service_names = self.dsl.get_service_names()
        self.assertEqual(service_names[0], "MyRest")

    def test_events(self):
        events = self.dsl.get_events()
        self.assertIn("create-vms", events[0]['name'])

    def test_tasks(self):
        tasks = self.dsl.get_tasks()
        self.assertIn("create-vms", tasks)
        self.assertIn("parameters", tasks["create-vms"])
        self.assertEqual(tasks["backup-vms"]["action"],
                         "Nova:backup-vm")

    def test_actions(self):
        action = self.dsl.get_action("MyRest:attach-volume")
        self.assertIn("method", action["parameters"])
        actions = self.dsl.get_actions("MyRest")
        self.assertIn("task-parameters", actions["attach-volume"])

    def test_broken_definition(self):
        broken_yaml = """
        Workflow:
          [tasks:
            create-vms/:

        """
        self.assertRaises(RuntimeError, dsl.Parser, broken_yaml)
