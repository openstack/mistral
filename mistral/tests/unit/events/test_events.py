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
from mistral import dsl
from mistral.tests.unit import base
from mistral import version


class EventsTest(base.DbTestCase):
    def setUp(self):
        super(EventsTest, self).setUp()
        self.doc = open(pkg.resource_filename(
            version.version_info.package,
            "tests/resources/test_rest.yaml")).read()
        self.dsl = dsl.Parser(self.doc)

    def test_events_create_after_wb_put(self):
        db_api.workbook_create({'name': 'my_workbook'})
        db_api.workbook_definition_put('my_workbook', self.doc)
        events = db_api.events_get(workbook_name='my_workbook')
        self.assertEqual(events[0]['name'], 'create-vms')
        self.assertEqual(events[0]['pattern'], '* * * * *')
        self.assertEqual(events[0]['workbook_name'], 'my_workbook')
