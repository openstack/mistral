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
import time
from unittest import mock

from oslo_config import cfg
from oslo_log import log as logging
from oslotest import base

from mistral import context as auth_context
from mistral.db.sqlalchemy import base as db_sa_base
from mistral.db.sqlalchemy import sqlite_lock
from mistral.db.v2 import api as db_api
from mistral.lang import parser as spec_parser
from mistral.services import actions as action_service
from mistral.services import security
from mistral.tests.unit import config as test_config
from mistral import version

RESOURCES_PATH = 'tests/resources/'
LOG = logging.getLogger(__name__)


test_config.parse_args()


def get_resource(resource_name):
    return open(pkg.resource_filename(
        version.version_info.package,
        RESOURCES_PATH + resource_name)).read()


def get_context(default=True, admin=False):
    if default:
        return auth_context.MistralContext.from_dict({
            'user_name': 'test-user',
            'user': '1-2-3-4',
            # TODO(tkajinam): Remove this once oslo.context >= 4.0.0 becomes
            #                 avaialble
            'tenant': security.DEFAULT_PROJECT_ID,
            'project_id': security.DEFAULT_PROJECT_ID,
            'project_name': 'test-project',
            'is_admin': admin
        })
    else:
        return auth_context.MistralContext.from_dict({
            'user_name': 'test-user',
            'user': '9-0-44-5',
            # TODO(tkajinam): Remove this once oslo.context >= 4.0.0 becomes
            #                 avaialble
            'tenant': '99-88-33',
            'project_id': '99-88-33',
            'project_name': 'test-another',
            'is_admin': admin
        })


class FakeHTTPResponse(object):
    def __init__(self, text, status_code, reason=None, headers=None,
                 history=None, encoding='utf-8', url='', cookies=None,
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

    def json(self, **kwargs):
        return json.loads(self.text, **kwargs)


class BaseTest(base.BaseTestCase):
    def setUp(self):
        super(BaseTest, self).setUp()

        # By default, retain only built-in actions so that the unit tests
        # don't see unexpected actions (i.e. provided by action generators
        # installed by other projects).
        self.override_config(
            'only_builtin_actions',
            True,
            'legacy_action_provider'
        )
        self.override_config(
            'load_action_generators',
            False,
            'legacy_action_provider'
        )

        self.addCleanup(spec_parser.clear_caches)

        def _cleanup_actions():
            action_service.get_test_action_provider().cleanup()

        self.addCleanup(_cleanup_actions)

    def register_action_class(self, name, cls):
        action_service.get_test_action_provider().register_python_action(
            name,
            cls
        )

    def assertRaisesWithMessage(self, exception, msg, func, *args, **kwargs):
        try:
            func(*args, **kwargs)
            self.assertFail()
        except exception as e:
            self.assertEqual(msg, e.message)

    def assertRaisesWithMessageContaining(self, exception, msg, func, *args,
                                          **kwargs):
        try:
            func(*args, **kwargs)
            self.assertFail()
        except exception as e:
            self.assertIn(msg, e.message)

    def assertListEqual(self, l1, l2):
        super(BaseTest, self).assertListEqual(l1, l2)

    def assertDictEqual(self, cmp1, cmp2):
        super(BaseTest, self).assertDictEqual(cmp1, cmp2)

    def _assert_single_item(self, items, **props):
        return self._assert_multiple_items(items, 1, **props)[0]

    def _assert_no_item(self, items, **props):
        self._assert_multiple_items(items, 0, **props)

    def _assert_multiple_items(self, items, count, **props):
        def _matches(item, **props):
            for prop_name, prop_val in props.items():
                v = item[prop_name] if isinstance(
                    item, dict) else getattr(item, prop_name)

                if v != prop_val:
                    return False

            return True

        filtered_items = list(
            [item for item in items if _matches(item, **props)]
        )

        found = len(filtered_items)

        if found != count:
            LOG.info("[failed test ctx] items=%s, expected_props=%s", str(
                items), props)
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

        for key, value in expected.items():
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

    def _await(self, predicate, delay=1, timeout=60, fail_message="no detail",
               fail_message_formatter=lambda x: x):
        """Awaits for predicate function to evaluate to True.

        If within a configured timeout predicate function hasn't evaluated
        to True then an exception is raised.
        :param predicate: Predicate function.
        :param delay: Delay in seconds between predicate function calls.
        :param timeout: Maximum amount of time to wait for predication
            function to evaluate to True.
        :param fail_message: explains what was expected
        :param fail_message_formatter: lambda that formats the fail_message
        :return:
        """
        end_time = time.time() + timeout

        while True:
            if predicate():
                break

            if time.time() + delay > end_time:
                raise AssertionError(
                    "Failed to wait for expected result: " +
                    fail_message_formatter(fail_message)
                )

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

    def _clean_db(self):
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
                    db_api.delete_action_definitions()
                    db_api.delete_environments()
                    db_api.delete_resource_members()
                    db_api.delete_delayed_calls()
                    db_api.delete_scheduled_jobs()

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
