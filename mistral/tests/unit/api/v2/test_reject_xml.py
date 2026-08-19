# Copyright 2026 - OVHcloud.
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

# An "XML entity expansion" ("billion laughs") payload. It must never
# reach the XML parser: the request has to be rejected upfront based on
# its content type.
XML_BOMB = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY nab "nab">
 <!ENTITY lol1 "&nab;&nab;&nab;&nab;&nab;&nab;&nab;&nab;&nab;&nab;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<lolz>&lol3;</lolz>"""


class TestRejectXML(base.APITest):
    """The API must reject XML request bodies with a 415.

    Mistral does not support XML and wsme deserializes XML bodies with an
    unhardened parser, so any XML content type has to be refused before
    the body is parsed. /v2/environments is used here because it is one
    of the wsme endpoints that deserialize a typed body.
    """

    def _assert_rejected(self, content_type):
        resp = self.app.post(
            '/v2/environments',
            XML_BOMB,
            headers={'Content-Type': content_type},
            expect_errors=True
        )

        self.assertEqual(415, resp.status_int)

    def test_text_xml_is_rejected(self):
        self._assert_rejected('text/xml')

    def test_application_xml_is_rejected(self):
        self._assert_rejected('application/xml')

    def test_xml_suffix_is_rejected(self):
        self._assert_rejected('application/foo+xml')

    def test_xml_with_charset_is_rejected(self):
        self._assert_rejected('text/xml; charset=utf-8')

    def test_json_is_not_rejected(self):
        # A JSON body must not be blocked: the payload is intentionally
        # invalid for an environment, so the request fails later with a
        # client error, but never with 415.
        resp = self.app.post_json(
            '/v2/environments',
            {'not': 'a valid environment'},
            expect_errors=True
        )

        self.assertNotEqual(415, resp.status_int)
