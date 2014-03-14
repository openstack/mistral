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

import tempfile

import unittest2
import pkg_resources as pkg
import os
from mistral import version
from mistral.db.sqlalchemy import api as db_api
from mistral.openstack.common.db.sqlalchemy import session


RESOURCES_PATH = 'tests/resources/'


def get_resource(resource_name):
    return open(pkg.resource_filename(
        version.version_info.package,
        RESOURCES_PATH + resource_name)).read()


class BaseTest(unittest2.TestCase):
    def setUp(self):
        super(BaseTest, self).setUp()

        # TODO: add whatever is needed for all Mistral tests in here

    def tearDown(self):
        super(BaseTest, self).tearDown()

        # TODO: add whatever is needed for all Mistral tests in here

    def _assert_single_item(self, items, **props):
        def _matches(item):
            for prop_name, prop_val in props.iteritems():
                v = item[prop_name] if isinstance(item, dict) \
                    else getattr(item, prop_name)

                if v != prop_val:
                    return False

            return True

        filtered_items = filter(_matches, items)

        if len(filtered_items) == 0:
            self.fail("Item not found [props=%s]" % props)

        if len(filtered_items) != 1:
            self.fail("Multiple items found [props=%s]" % props)

        return filtered_items[0]


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
