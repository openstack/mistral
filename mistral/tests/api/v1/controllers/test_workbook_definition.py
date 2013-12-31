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

import mock

from mistral.tests.api import base
from mistral.db import api as db_api

# TODO: later we need additional tests verifying all the errors etc.

DEFINITION = "my definition"


class TestWorkbookDefinitionController(base.FunctionalTest):
    def setUp(self):
        super(TestWorkbookDefinitionController, self).setUp()
        self.workbook_definition_put = db_api.workbook_definition_put
        self.workbook_definition_get = db_api.workbook_definition_get

    def tearDown(self):
        super(TestWorkbookDefinitionController, self).tearDown()
        db_api.workbook_definition_put = self.workbook_definition_put
        db_api.workbook_definition_get = self.workbook_definition_get

    def test_get(self):
        db_api.workbook_definition_get = \
            mock.MagicMock(return_value=DEFINITION)

        resp = self.app.get('/v1/workbooks/my_workbook/definition',
                            headers={"Content-Type": "text/plain"})

        self.assertEqual(resp.status_int, 200)
        self.assertEqual(DEFINITION, resp.text)

    def test_put(self):
        new_definition = """
        Workflow:
            events:
                create-vms:
                    type: periodic
                    tasks: create-vms
                    parameters:
                        cron-pattern: "* * * * *"
        """

        db_api.workbook_definition_put = \
            mock.MagicMock(return_value={
                'name': 'my_workbook',
                'definition': new_definition
            })

        resp = self.app.put('/v1/workbooks/my_workbook/definition',
                            new_definition,
                            headers={"Content-Type": "text/plain"})

        self.assertEqual(resp.status_int, 200)
        self.assertEqual(new_definition, resp.body)

        # Check that associated events have been created in DB.
        events = db_api.events_get(workbook_name='my_workbook')

        self.assertEqual(events[0]['name'], 'create-vms')
        self.assertEqual(events[0]['pattern'], '* * * * *')
        self.assertEqual(events[0]['workbook_name'], 'my_workbook')
