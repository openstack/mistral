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


from mistral.tests.unit.api import base

FILE_CONTENT = """test file"""

UPDATED_FILE_CONTENT = """updated content"""

MODULE_NAME = 'modulename%s'
NAMESPACE = "NS"


class TestCodeSourcesController(base.APITest):
    def _create_code_source(self, module_name, file_content,
                            namespace=NAMESPACE, expect_errors=False):
        return self.app.post(
            '/v2/code_sources',
            params={'namespace': namespace},
            upload_files=[
                (module_name, 'filename', file_content.encode())
            ],
            expect_errors=expect_errors
        )

    def _delete_code_source(self, id, namespace=NAMESPACE):
        return self.app.delete(
            '/v2/code_sources/%s?namespace=%s' % (id, namespace)
        )

    def test_create_code_source(self):
        mod_name = MODULE_NAME % 'create'

        resp = self._create_code_source(
            mod_name,
            FILE_CONTENT
        )

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        code_sources = resp_json.get('code_sources')

        self.assertEqual(1, len(code_sources))

        code_source = code_sources[0]

        self.assertEqual(mod_name, code_source.get('name'))
        self.assertEqual(FILE_CONTENT, code_source.get('src'))
        self.assertEqual(1, code_source.get('version'))
        self.assertEqual(NAMESPACE, code_source.get('namespace'))

        self._delete_code_source(mod_name)

    def test_update_code_source(self):
        mod_name = MODULE_NAME % 'update'

        self._create_code_source(mod_name, FILE_CONTENT)
        resp = self.app.put(
            '/v2/code_sources/',
            params='namespace=%s' % NAMESPACE,
            upload_files=[
                (mod_name, 'filename', UPDATED_FILE_CONTENT.encode())
            ],
        )

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        code_sources = resp_json.get('code_sources')

        self.assertEqual(1, len(code_sources))

        code_source = code_sources[0]

        self.assertEqual(200, resp.status_int)

        self.assertEqual(mod_name, code_source.get('name'))
        self.assertEqual(UPDATED_FILE_CONTENT, code_source.get('src'))
        self.assertEqual(2, code_source.get('version'))
        self.assertEqual(NAMESPACE, code_source.get('namespace'))

        self._delete_code_source(mod_name)

    def test_delete_code_source(self):
        mod_name = MODULE_NAME % 'delete'
        resp = self._create_code_source(mod_name, FILE_CONTENT)

        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        code_sources = resp_json.get('code_sources')

        self.assertEqual(1, len(code_sources))

        self._delete_code_source(mod_name)

    def test_create_duplicate_code_source(self):
        mod_name = MODULE_NAME % 'duplicate'
        self._create_code_source(mod_name, FILE_CONTENT)
        resp = self._create_code_source(
            mod_name,
            FILE_CONTENT, expect_errors=True
        )

        self.assertEqual(409, resp.status_int)
        self.assertIn('Duplicate entry for CodeSource', resp)
        self._delete_code_source(mod_name)

    def test_get_code_source(self):
        mod_name = MODULE_NAME % 'get'
        self._create_code_source(mod_name, FILE_CONTENT)

        resp = self.app.get(
            '/v2/code_sources/%s' % mod_name,
            params='namespace=%s' % NAMESPACE
        )
        resp_json = resp.json

        self.assertEqual(200, resp.status_int)

        self.assertEqual(mod_name, resp_json.get('name'))
        self.assertEqual(FILE_CONTENT, resp_json.get('src'))
        self.assertEqual(1, resp_json.get('version'))
        self.assertEqual(NAMESPACE, resp_json.get('namespace'))

        self._delete_code_source(mod_name)

    def test_get_all_code_source(self):
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

        code_sources = resp_json.get('code_sources')

        self.assertEqual(2, len(code_sources))

        self._delete_code_source(mod_name)
        self._delete_code_source(mod2_name)
