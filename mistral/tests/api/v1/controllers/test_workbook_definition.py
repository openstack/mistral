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

from mistral.db import api as db_api
from mistral import exceptions
from mistral.tests.api import base

DEFINITION = "my definition"

NEW_DEFINITION = """
Namespaces:
  Service:
    actions:
      action:
        class: std.echo
        base-parameters:
            output: Haha

Workflow:
  tasks:
    task1:
      parameters:
      action: Service:action

triggers:
  create-vms:
    type: periodic
    tasks: create-vms
    parameters:
      cron-pattern: "* * * * *"
"""


class TestWorkbookDefinitionController(base.FunctionalTest):
    @mock.patch.object(db_api, "workbook_definition_get",
                       mock.MagicMock(return_value=DEFINITION))
    def test_get(self):
        resp = self.app.get('/v1/workbooks/my_workbook/definition',
                            headers={"Content-Type": "text/plain"})

        self.assertEqual(resp.status_int, 200)
        self.assertEqual(DEFINITION, resp.text)

    @mock.patch.object(db_api, "workbook_definition_get",
                       mock.MagicMock(
                           side_effect=exceptions.NotFoundException()))
    def test_get_not_found(self):
        resp = self.app.get('/v1/workbooks/my_workbook/definition',
                            headers={"Content-Type": "text/plain"},
                            expect_errors=True)

        self.assertEqual(resp.status_int, 404)

    @mock.patch.object(db_api, "workbook_definition_put",
                       mock.MagicMock(return_value={
                           'name': 'my_workbook',
                           'definition': NEW_DEFINITION
                       }))
    def test_put(self):
        resp = self.app.put('/v1/workbooks/my_workbook/definition',
                            NEW_DEFINITION,
                            headers={"Content-Type": "text/plain"})

        self.assertEqual(resp.status_int, 200)
        self.assertEqual(NEW_DEFINITION, resp.body)

        # Check that associated triggers have been created in DB.
        triggers = db_api.triggers_get(workbook_name='my_workbook')

        self.assertEqual(triggers[0]['name'], 'create-vms')
        self.assertEqual(triggers[0]['pattern'], '* * * * *')
        self.assertEqual(triggers[0]['workbook_name'], 'my_workbook')

    @mock.patch.object(db_api, "workbook_definition_put",
                       mock.MagicMock(
                           side_effect=exceptions.NotFoundException()))
    def test_put_not_found(self):
        resp = self.app.put('/v1/workbooks/my_workbook/definition',
                            NEW_DEFINITION,
                            headers={"Content-Type": "text/plain"},
                            expect_errors=True)

        self.assertEqual(resp.status_int, 404)
