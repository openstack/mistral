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

import os
import tempfile
import unittest2

from oslo import messaging
from oslo.config import cfg
from oslo.messaging import transport
import pkg_resources as pkg
from stevedore import driver

from mistral.openstack.common import importutils


# We need to make sure that all configuration properties are registered.
importutils.import_module("mistral.config")

from mistral.db.sqlalchemy import api as db_api
from mistral.openstack.common import log as logging
from mistral.openstack.common.db.sqlalchemy import session
from mistral import version
from mistral.engine import client
from mistral.engine.scalable import engine
from mistral.engine.scalable.executor import server


RESOURCES_PATH = 'tests/resources/'
LOG = logging.getLogger(__name__)


def get_resource(resource_name):
    return open(pkg.resource_filename(
        version.version_info.package,
        RESOURCES_PATH + resource_name)).read()


def get_fake_transport():
    # Get transport here to let oslo.messaging setup default config
    # before changing the rpc_backend to the fake driver; otherwise,
    # oslo.messaging will throw exception.
    messaging.get_transport(cfg.CONF)
    cfg.CONF.set_default('rpc_backend', 'fake')
    url = transport.TransportURL.parse(cfg.CONF, None, None)
    kwargs = dict(default_exchange=cfg.CONF.control_exchange,
                  allowed_remote_exmods=[])
    mgr = driver.DriverManager('oslo.messaging.drivers',
                               url.transport,
                               invoke_on_load=True,
                               invoke_args=[cfg.CONF, url],
                               invoke_kwds=kwargs)
    return transport.Transport(mgr.driver)


class BaseTest(unittest2.TestCase):
    def setUp(self):
        super(BaseTest, self).setUp()

        # TODO: add whatever is needed for all Mistral tests in here

    def tearDown(self):
        super(BaseTest, self).tearDown()

        # TODO: add whatever is needed for all Mistral tests in here

    def _assert_single_item(self, items, **props):
        return self._assert_multiple_items(items, 1, **props)[0]

    def _assert_multiple_items(self, items, count, **props):
        def _matches(item, **props):
            for prop_name, prop_val in props.iteritems():
                v = item[prop_name] if isinstance(item, dict) \
                    else getattr(item, prop_name)

                if v != prop_val:
                    return False

            return True

        filtered_items = filter(lambda item: _matches(item, **props), items)

        found = len(filtered_items)

        if found != count:
            LOG.info("[failed test ctx] items=%s, expected_props=%s" % (str(
                items), props))
            self.fail("Wrong number of items found [props=%s, "
                      "expected=%s, found=%s]" % (props, count, found))

        return filtered_items


class DbTestCase(BaseTest):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        session.set_defaults('sqlite:///' + self.db_path, self.db_path)
        db_api.setup_db()

    def tearDown(self):
        db_api.drop_db()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def is_db_session_open(self):
        return db_api._get_thread_local_session() is not None


class EngineTestCase(DbTestCase):
    transport = get_fake_transport()

    def __init__(self, *args, **kwargs):
        super(EngineTestCase, self).__init__(*args, **kwargs)
        self.engine = client.EngineClient(self.transport)

    @classmethod
    def mock_task_result(cls, workbook_name, execution_id,
                         task_id, state, result):
        """
        Mock the engine convey_task_results to send request directly
        to the engine instead of going through the oslo.messaging transport.
        """
        return engine.ScalableEngine.convey_task_result(
            workbook_name, execution_id, task_id, state, result)

    @classmethod
    def mock_start_workflow(cls, workbook_name, task_name, context=None):
        """
        Mock the engine start_workflow_execution to send request directly
        to the engine instead of going through the oslo.messaging transport.
        """
        return engine.ScalableEngine.start_workflow_execution(
            workbook_name, task_name, context)

    @classmethod
    def mock_get_workflow_state(cls, workbook_name, execution_id):
        """
        Mock the engine get_workflow_execution_state to send request directly
        to the engine instead of going through the oslo.messaging transport.
        """
        return engine.ScalableEngine.get_workflow_execution_state(
            workbook_name, execution_id)

    @classmethod
    def mock_run_tasks(cls, tasks):
        """
        Mock the engine _run_tasks to send requests directly to the task
        executor instead of going through the oslo.messaging transport.
        """
        executor = server.Executor(transport=cls.transport)
        for task in tasks:
            executor.handle_task({}, task=task)

    @classmethod
    def mock_handle_task(cls, cntx, **kwargs):
        """
        Mock the executor handle_task to send requests directory to the task
        executor instead of going through the oslo.messaging transport.
        """
        executor = server.Executor(transport=cls.transport)
        return executor.handle_task(cntx, **kwargs)
