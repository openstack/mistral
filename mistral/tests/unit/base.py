# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

import datetime
import json
import pkg_resources as pkg
import sys
import time

import mock
from oslo_config import cfg
from oslo_log import log as logging
from oslotest import base
import six
import testtools.matchers as ttm

from mistral import context as auth_context
from mistral.db.sqlalchemy import base as db_sa_base
from mistral.db.sqlalchemy import sqlite_lock
from mistral.db.v2 import api as db_api
from mistral.services import action_manager
from mistral.services import security
from mistral.tests.unit import config as test_config
from mistral.utils import inspect_utils as i_utils
from mistral import version
from mistral.workbook import parser as spec_parser
from mistral.workflow import lookup_utils

RESOURCES_PATH = 'tests/resources/'
LOG = logging.getLogger(__name__)


test_config.parse_args()


def get_resource(resource_name):
    return open(pkg.resource_filename(
        version.version_info.package,
        RESOURCES_PATH + resource_name)).read()


def get_context(default=True, admin=False):
    if default:
        return auth_context.MistralContext(
            user_id='1-2-3-4',
            project_id=security.DEFAULT_PROJECT_ID,
            user_name='test-user',
            project_name='test-project',
            is_admin=admin
        )
    else:
        return auth_context.MistralContext(
            user_id='9-0-44-5',
            project_id='99-88-33',
            user_name='test-user',
            project_name='test-another',
            is_admin=admin
        )


def register_action_class(name, cls, attributes=None, desc=None):
    action_manager.register_action_class(
        name,
        '%s.%s' % (cls.__module__, cls.__name__),
        attributes or {},
        input_str=i_utils.get_arg_list_as_str(cls.__init__)
    )


class FakeHTTPResponse(object):
    def __init__(self, text, status_code, reason=None, headers=None,
                 history=None, encoding='utf8', url='', cookies=None,
                 elapsed=None):
        self.text = text
        self.content = text
        self.status_code = status_code
        self.reason = reason
        self.headers = headers or {}
        self.history = history
        self.encoding = encoding
        self.url = url
        self.cookies = cookies or {}
        self.elapsed = elapsed or datetime.timedelta(milliseconds=123)

    def json(self):
        return json.loads(self.text)


class BaseTest(base.BaseTestCase):
    def setUp(self):
        super(BaseTest, self).setUp()

        self.addCleanup(spec_parser.clear_caches)

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
            for prop_name, prop_val in six.iteritems(props):
                v = item[prop_name] if isinstance(
                    item, dict) else getattr(item, prop_name)

                if v != prop_val:
                    return False

            return True

        filtered_items = list(
            filter(lambda item: _matches(item, **props), items)
        )

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

        for key, value in six.iteritems(expected):
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

    def override_config(self, name, override, group=None):
        """Cleanly override CONF variables."""
        cfg.CONF.set_override(name, override, group)
        self.addCleanup(cfg.CONF.clear_override, name, group)


class DbTestCase(BaseTest):
    is_heavy_init_called = False

    @classmethod
    def __heavy_init(cls):
        """Method that runs heavy_init().

        Make this method private to prevent extending this one.
        It runs heavy_init() only once.

        Note: setUpClass() can be used, but it magically is not invoked
        from child class in another module.
        """
        if not cls.is_heavy_init_called:
            cls.heavy_init()
            cls.is_heavy_init_called = True

    @classmethod
    def heavy_init(cls):
        """Runs a long initialization.

        This method runs long initialization  once by class
        and can be extended by child classes.
        """
        # If using sqlite, change to memory. The default is file based.
        if cfg.CONF.database.connection.startswith('sqlite'):
            cfg.CONF.set_default('connection', 'sqlite://', group='database')

        cfg.CONF.set_default('max_overflow', -1, group='database')
        cfg.CONF.set_default('max_pool_size', 1000, group='database')

        db_api.setup_db()

        action_manager.sync_db()

    def _clean_db(self):
        lookup_utils.clean_caches()

        contexts = [
            get_context(default=False),
            get_context(default=True)
        ]

        for ctx in contexts:
            auth_context.set_ctx(ctx)

            with mock.patch('mistral.services.security.get_project_id',
                            new=mock.MagicMock(return_value=ctx.project_id)):
                with db_api.transaction():
                    db_api.delete_event_triggers()
                    db_api.delete_cron_triggers()
                    db_api.delete_workflow_executions()
                    db_api.delete_task_executions()
                    db_api.delete_action_executions()
                    db_api.delete_workbooks()
                    db_api.delete_workflow_definitions()
                    db_api.delete_environments()
                    db_api.delete_resource_members()
                    db_api.delete_delayed_calls()

        sqlite_lock.cleanup()

        if not cfg.CONF.database.connection.startswith('sqlite'):
            db_sa_base.get_engine().dispose()

    def setUp(self):
        super(DbTestCase, self).setUp()

        self.__heavy_init()

        self.ctx = get_context()
        auth_context.set_ctx(self.ctx)

        self.addCleanup(auth_context.set_ctx, None)
        self.addCleanup(self._clean_db)

    def is_db_session_open(self):
        return db_sa_base._get_thread_local_session() is not None
