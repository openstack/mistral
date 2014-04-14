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

from mistral.db import api as db_api
from mistral.tests import base
from mistral import version
from mistral.services import scheduler


class TriggersTest(base.DbTestCase):
    def setUp(self):
        super(TriggersTest, self).setUp()

        self.doc = open(pkg.resource_filename(
            version.version_info.package,
            "tests/resources/test_rest.yaml")).read()

    def test_create_associated_triggers(self):
        workbook = {
            'name': 'my_workbook',
            'definition': self.doc
        }

        scheduler.create_associated_triggers(workbook)

        triggers = db_api.triggers_get(workbook_name='my_workbook')

        self.assertEqual(triggers[0]['name'], 'create-vms')
        self.assertEqual(triggers[0]['pattern'], '* * * * *')
        self.assertEqual(triggers[0]['workbook_name'], 'my_workbook')
