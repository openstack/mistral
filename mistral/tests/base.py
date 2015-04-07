# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
import sys
import time

from oslo.config import cfg
from oslotest import base
import testtools.matchers as ttm

from mistral import context as auth_context
from mistral.db.sqlalchemy import base as db_sa_base
from mistral.db.sqlalchemy import sqlite_lock
from mistral.db.v2 import api as db_api_v2
from mistral.openstack.common import log as logging
from mistral.services import action_manager
from mistral import version


RESOURCES_PATH = 'tests/resources/'
LOG = logging.getLogger(__name__)


def get_resource(resource_name):
    return open(pkg.resource_filename(
        version.version_info.package,
        RESOURCES_PATH + resource_name)).read()


class BaseTest(base.BaseTestCase):
    def assertListEqual(self, l1, l2):
        if tuple(sys.version_info)[0:2] < (2, 7):
            # for python 2.6 compatibility
            self.assertEqual(l1, l2)
        else:
            super(BaseTest, self).assertListEqual(l1, l2)

    def assertDictEqual(self, cmp1, cmp2):
        if tuple(sys.version_info)[0:2] < (2, 7):
            # for python 2.6 compatibility
            self.assertThat(cmp1, ttm.Equals(cmp2))
        else:
            super(BaseTest, self).assertDictEqual(cmp1, cmp2)

    def _assert_single_item(self, items, **props):
        return self._assert_multiple_items(items, 1, **props)[0]

    def _assert_multiple_items(self, items, count, **props):
        def _matches(item, **props):
            for prop_name, prop_val in props.iteritems():
                v = item[prop_name] if isinstance(
                    item, dict) else getattr(item, prop_name)

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

    def _assert_dict_contains_subset(self, expected, actual, msg=None):
        """Checks whether actual is a superset of expected.

        Note: This is almost the exact copy of the standard method
        assertDictContainsSubset() that appeared in Python 2.7, it was
        added to use it with Python 2.6.
        """
        missing = []
        mismatched = []

        for key, value in expected.iteritems():
            if key not in actual:
                missing.append(key)
            elif value != actual[key]:
                mismatched.append('%s, expected: %s, actual: %s' %
                                  (key, value,
                                   actual[key]))

        if not (missing or mismatched):
            return

        standardMsg = ''

        if missing:
            standardMsg = 'Missing: %s' % ','.join(m for m in missing)
        if mismatched:
            if standardMsg:
                standardMsg += '; '
            standardMsg += 'Mismatched values: %s' % ','.join(mismatched)

        self.fail(self._formatMessage(msg, standardMsg))

    def _await(self, predicate, delay=1, timeout=60):
        """Awaits for predicate function to evaluate to True.

        If within a configured timeout predicate function hasn't evaluated
        to True then an exception is raised.
        :param predicate: Predication function.
        :param delay: Delay in seconds between predicate function calls.
        :param timeout: Maximum amount of time to wait for predication
            function to evaluate to True.
        :return:
        """
        end_time = time.time() + timeout

        while True:
            if predicate():
                break

            if time.time() + delay > end_time:
                raise AssertionError("Failed to wait for expected result.")

            time.sleep(delay)

    def _sleep(self, seconds):
        time.sleep(seconds)


class DbTestCase(BaseTest):
    is_heavy_init_called = False

    @classmethod
    def __heavy_init(cls):
        """Make this method private to prevent extending this one.
        It runs heavy_init() only once.

        Note: setUpClass() can be used, but it magically is not invoked
        from child class in another module.
        """
        if not cls.is_heavy_init_called:
            cls.heavy_init()
            cls.is_heavy_init_called = True

    @classmethod
    def heavy_init(cls):
        """Runs a long initialization (runs once by class)
        and can be extended by child classes.
        """
        cfg.CONF.set_default('connection', 'sqlite://', group='database')
        cfg.CONF.set_default('max_overflow', -1, group='database')
        cfg.CONF.set_default('max_pool_size', 1000, group='database')

        db_api_v2.setup_db()

        action_manager.sync_db()

    def _clean_db(self):
        with db_api_v2.transaction():
            db_api_v2.delete_workbooks()
            db_api_v2.delete_executions()
            db_api_v2.delete_cron_triggers()
            db_api_v2.delete_workflow_definitions()

        sqlite_lock.cleanup()

    def setUp(self):
        super(DbTestCase, self).setUp()

        self.__heavy_init()

        self.ctx = auth_context.MistralContext(
            user_id='1-2-3-4',
            project_id='<default-project>',
            user_name='test-user',
            project_name='test-project',
            is_admin=False
        )

        auth_context.set_ctx(self.ctx)

        self.addCleanup(auth_context.set_ctx, None)
        self.addCleanup(self._clean_db)

    def is_db_session_open(self):
        return db_sa_base._get_thread_local_session() is not None
