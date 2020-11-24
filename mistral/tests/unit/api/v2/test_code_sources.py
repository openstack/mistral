# Copyright 2020 - Nokia Software.
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


from mistral.db.v2 import api as db_api
from mistral.tests.unit.api import base

FILE_CONTENT = "test file"

UPDATED_FILE_CONTENT = "updated content"

MODULE_NAME = 'modulename%s'
NAMESPACE = "NS"


class TestCodeSourcesController(base.APITest):
    def _create_code_source(self, module_name, file_content,
                            namespace=NAMESPACE, expect_errors=False):
        return self.app.post(
            '/v2/code_sources?name=%s&namespace=%s' % (module_name, namespace),
            file_content,
            headers={'Content-Type': 'text/plain'},
            expect_errors=expect_errors
        )

    def _delete_code_source(self, id, namespace=NAMESPACE):
        return self.app.delete(
            '/v2/code_sources/%s?namespace=%s' % (id, namespace)
        )

    def setUp(self):
        super(TestCodeSourcesController, self).setUp()

        self.addCleanup(db_api.delete_code_sources)

    def test_post(self):
        mod_name = MODULE_NAME % 'create'

        resp = self._create_code_source(mod_name, FILE_CONTENT)

        self.assertEqual(201, resp.status_int)

        code_src = resp.json

        self.assertEqual(mod_name, code_src['name'])
        self.assertEqual(FILE_CONTENT, code_src['content'])
        self.assertEqual(1, code_src['version'])
        self.assertEqual(NAMESPACE, code_src['namespace'])

    def test_put(self):
        mod_name = MODULE_NAME % 'update'

        self._create_code_source(mod_name, FILE_CONTENT)

        resp = self.app.put(
            '/v2/code_sources?identifier=%s&namespace=%s' %
            (mod_name, NAMESPACE),
            UPDATED_FILE_CONTENT,
            headers={'Content-Type': 'text/plain'}
        )

        self.assertEqual(200, resp.status_int)

        code_src = resp.json

        self.assertEqual(mod_name, code_src['name'])
        self.assertEqual(UPDATED_FILE_CONTENT, code_src['content'])
        self.assertEqual(2, code_src['version'])
        self.assertEqual(NAMESPACE, code_src['namespace'])

    def test_delete(self):
        mod_name = MODULE_NAME % 'delete'

        resp = self._create_code_source(mod_name, FILE_CONTENT)

        self.assertEqual(201, resp.status_int)
        self.assertEqual(mod_name, resp.json['name'])

        # Make sure the object is in DB.
        self.assertIsNotNone(
            db_api.load_code_source(mod_name, namespace=NAMESPACE)
        )

        self._delete_code_source(mod_name)

        # Make sure the object was deleted from DB.
        self.assertIsNone(
            db_api.load_code_source(mod_name, namespace=NAMESPACE)
        )

    def test_post_duplicate(self):
        mod_name = MODULE_NAME % 'duplicate'

        self._create_code_source(mod_name, FILE_CONTENT)

        resp = self._create_code_source(
            mod_name,
            FILE_CONTENT, expect_errors=True
        )

        self.assertEqual(409, resp.status_int)
        self.assertIn('Duplicate entry for CodeSource', resp)

        self._delete_code_source(mod_name)

    def test_get(self):
        mod_name = MODULE_NAME % 'get'

        self._create_code_source(mod_name, FILE_CONTENT)

        resp = self.app.get(
            '/v2/code_sources/%s?namespace=%s' % (mod_name, NAMESPACE)
        )

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        self.assertEqual(mod_name, resp_json['name'])
        self.assertEqual(FILE_CONTENT, resp_json['content'])
        self.assertEqual(1, resp_json['version'])
        self.assertEqual(NAMESPACE, resp_json['namespace'])

    def test_get_all(self):
        mod_name = MODULE_NAME % 'getall'
        mod2_name = MODULE_NAME % '2getall'

        self._create_code_source(mod_name, FILE_CONTENT)
        self._create_code_source(mod2_name, FILE_CONTENT)

        resp = self.app.get(
            '/v2/code_sources',
            params='namespace=%s' % NAMESPACE
        )

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        code_sources = resp_json['code_sources']

        self.assertEqual(2, len(code_sources))
