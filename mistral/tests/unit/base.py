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

from mistral.db.sqlalchemy import api as db_api
from mistral.openstack.common.db.sqlalchemy import session


class DbTestCase(unittest2.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        session.set_defaults('sqlite:///' + self.db_path, self.db_path)
        db_api.setup_db()

    def tearDown(self):
        db_api.drop_db()
        os.close(self.db_fd)
        os.unlink(self.db_path)
