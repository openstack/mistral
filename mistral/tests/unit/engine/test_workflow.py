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

from mistral import dsl
from mistral import version
from mistral.tests import base
from mistral.engine import states
from mistral.engine import workflow

TASKS = [
    {
        'requires': {},
        'name': 'backup-vms',
        'state': states.IDLE
    },
    {
        'requires': {},
        'name': 'create-vms',
        'state': states.SUCCESS
    },
    {
        'requires': {'create-vms': ''},
        'name': 'attach-volume',
        'state': states.IDLE
    }
]


class WorkflowTest(base.DbTestCase):
    def setUp(self):
        super(WorkflowTest, self).setUp()
        self.doc = open(pkg.resource_filename(
            version.version_info.package,
            "tests/resources/test_rest.yaml")).read()
        self.parser = dsl.Parser(self.doc)

    def test_find_workflow_tasks(self):
        tasks = workflow.find_workflow_tasks(self.parser, "attach-volumes")
        self.assertEqual(tasks[1]['name'], 'create-vms')

    def test_tasks_to_start(self):
        tasks_to_start = workflow.find_resolved_tasks(TASKS)
        self.assertEqual(len(tasks_to_start), 2)
