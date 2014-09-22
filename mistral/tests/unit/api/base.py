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
from oslo.config import cfg
import pecan
import pecan.testing
from webtest import app as webtest_app

from mistral.db.v1.sqlalchemy import models
from mistral.tests import base

# Disable authentication for functional tests.
cfg.CONF.set_default('auth_enable', False, group='pecan')

__all__ = ['FunctionalTest']


# Group of methods to mock DB API calls.

def create_db_workbook(values):
    wb = models.Workbook()
    wb.update(values)
    return wb


def create_mock_workbook(values):
    return mock.MagicMock(return_value=create_db_workbook(values))


def create_mock_workbooks(arr_of_values):
    return mock.MagicMock(
        return_value=[create_db_workbook(values) for values in arr_of_values]
    )


def create_db_execution(values):
    ex = models.WorkflowExecution()
    ex.update(values)
    return ex


def create_mock_execution(values):
    return mock.MagicMock(return_value=create_db_execution(values))


def create_mock_executions(arr_of_values):
    return mock.MagicMock(
        return_value=[create_db_execution(values) for values in arr_of_values]
    )


def create_db_task(values):
    t = models.Task()
    t.update(values)
    return t


def create_mock_task(values):
    return mock.MagicMock(return_value=create_db_task(values))


def create_mock_tasks(arr_of_values):
    return mock.MagicMock(
        return_value=[create_db_task(values) for values in arr_of_values]
    )


class FunctionalTest(base.DbTestCase):
    """Used for functional tests where you need to test your
    literal application and its integration with the framework.
    """

    def setUp(self):
        super(FunctionalTest, self).setUp()

        pecan_opts = cfg.CONF.pecan

        self.app = pecan.testing.load_test_app({
            'app': {
                'root': pecan_opts.root,
                'modules': pecan_opts.modules,
                'debug': pecan_opts.debug,
                'auth_enable': False
            }
        })
        self.addCleanup(pecan.set_config, {}, overwrite=True)
        self.addCleanup(cfg.CONF.set_default, 'auth_enable', False,
                        group='pecan')

        # make sure the api get the correct context.
        self.patch_ctx = mock.patch('mistral.context.context_from_headers')
        self.mock_ctx = self.patch_ctx.start()
        self.mock_ctx.return_value = self.ctx
        self.addCleanup(self.patch_ctx.stop)

    def assertNotFound(self, url):
        try:
            self.app.get(url, headers={'Accept': 'application/json'})
        except webtest_app.AppError as error:
            self.assertIn('Bad response: 404 Not Found', str(error))

            return

        self.fail('Expected 404 Not found but got OK')

    def assertUnauthorized(self, url):
        try:
            self.app.get(url, headers={'Accept': 'application/json'})
        except webtest_app.AppError as error:
            self.assertIn('Bad response: 401 Unauthorized', str(error))

            return

        self.fail('Expected 401 Unauthorized but got OK')
