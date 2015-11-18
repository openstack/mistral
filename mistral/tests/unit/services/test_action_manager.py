# Copyright 2014 - Mirantis, Inc.
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
from mistral.tests.unit import base


class ActionManagerTest(base.DbTestCase):
    def test_action_input(self):
        std_http = db_api.get_action_definition("std.http")
        std_email = db_api.get_action_definition("std.email")

        http_action_input = (
            'url, method="GET", params=null, body=null, '
            'headers=null, cookies=null, auth=null, '
            'timeout=null, allow_redirects=null, '
            'proxies=null, verify=null'
        )

        self.assertEqual(http_action_input, std_http.input)

        std_email_input = (
            "from_addr, to_addrs, smtp_server, "
            "smtp_password, subject=null, body=null"
        )

        self.assertEqual(std_email_input, std_email.input)

    def test_action_description(self):
        std_http = db_api.get_action_definition("std.http")
        std_echo = db_api.get_action_definition("std.echo")

        self.assertIn("Constructs an HTTP action", std_http.description)
        self.assertIn("param body: (optional) Dictionary, bytes",
                      std_http.description)

        self.assertIn("This action just returns a configured value",
                      std_echo.description)
