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

from mistral.openstack.common import jsonutils
from mistral.tests.api import base


class TestWorkbooksController(base.FunctionalTest):

    def test_get_all(self):
        resp = self.app.get('/v1/workbooks',
                            headers={'Accept': 'application/json'})

        self.assertEqual(resp.status_int, 200)

        data = jsonutils.loads(resp.body.decode())

        print "json=%s" % data

        #self.assertEqual(data['name'], 'my_workbook')
        #self.assertEqual(data['description'], 'My cool workbook')
