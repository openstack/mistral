# -*- coding: utf-8 -*-
#
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

import base64
from email.header import decode_header
from email import parser
import mock
import six
import testtools

from mistral.actions import std_actions as std
from mistral import exceptions as exc
from mistral.tests.unit import base

"""
To try against a real SMTP server:

1) set LOCAL_SMTPD = True
   run debug smtpd on the local machine:
   `sudo python -m smtpd -c DebuggingServer -n localhost:25`
   Debugging server doesn't support password.

2) set REMOTE_SMTP = True
   use external SMTP (like gmail), change the configuration,
   provide actual username and password

   self.settings = {
       'host': 'smtp.gmail.com:587',
       'from': 'youraccount@gmail.com',
       'password': 'secret'
   }
"""

LOCAL_SMTPD = False
REMOTE_SMTP = False


class SendEmailActionTest(base.BaseTest):

    def setUp(self):
        super(SendEmailActionTest, self).setUp()
        self.to_addrs = ["dz@example.com", "deg@example.com",
                         "xyz@example.com"]
        self.subject = "Multi word subject с русскими буквами"
        self.body = "short multiline\nbody\nc русскими буквами"

        self.smtp_server = 'mail.example.com:25'
        self.from_addr = "bot@example.com"

        self.to_addrs_str = ", ".join(self.to_addrs)

    @testtools.skipIf(not LOCAL_SMTPD, "Setup local smtpd to run it")
    def test_send_email_real(self):
        action = std.SendEmailAction(
            self.from_addr, self.to_addrs,
            self.smtp_server, None, self.subject, self.body
        )
        action.run()

    @testtools.skipIf(not REMOTE_SMTP, "Configure Remote SMTP to run it")
    def test_with_password_real(self):
        self.to_addrs = ["dz@stackstorm.com"]
        self.smtp_server = 'mail.example.com:25'
        self.from_addr = "bot@example.com"
        self.smtp_password = 'secret'

        action = std.SendEmailAction(
            self.from_addr, self.to_addrs,
            self.smtp_server, self.smtp_password, self.subject, self.body
        )

        action.run()

    @mock.patch('smtplib.SMTP')
    def test_with_mutli_to_addrs(self, smtp):
        smtp_password = "secret"
        action = std.SendEmailAction(
            self.from_addr, self.to_addrs,
            self.smtp_server, smtp_password, self.subject, self.body
        )
        action.run()

    @mock.patch('smtplib.SMTP')
    def test_with_one_to_addr(self, smtp):
        to_addr = ["dz@example.com"]
        smtp_password = "secret"

        action = std.SendEmailAction(
            self.from_addr, to_addr,
            self.smtp_server, smtp_password, self.subject, self.body
        )
        action.run()

    @mock.patch('smtplib.SMTP')
    def test_send_email(self, smtp):
        action = std.SendEmailAction(
            self.from_addr, self.to_addrs,
            self.smtp_server, None, self.subject, self.body
        )

        action.run()

        smtp.assert_called_once_with(self.smtp_server)

        sendmail = smtp.return_value.sendmail

        self.assertTrue(sendmail.called, "should call sendmail")
        self.assertEqual(
            self.from_addr, sendmail.call_args[1]['from_addr'])
        self.assertEqual(
            self.to_addrs, sendmail.call_args[1]['to_addrs'])

        message = parser.Parser().parsestr(sendmail.call_args[1]['msg'])

        self.assertEqual(self.from_addr, message['from'])
        self.assertEqual(self.to_addrs_str, message['to'])
        if six.PY3:
            self.assertEqual(
                self.subject,
                decode_header(message['subject'])[0][0].decode('utf-8')
            )
        else:
            self.assertEqual(
                self.subject.decode('utf-8'),
                decode_header(message['subject'])[0][0].decode('utf-8')
            )
        if six.PY3:
            self.assertEqual(
                self.body,
                base64.b64decode(message.get_payload()).decode('utf-8')
            )
        else:
            self.assertEqual(
                self.body.decode('utf-8'),
                base64.b64decode(message.get_payload()).decode('utf-8')
            )

    @mock.patch('smtplib.SMTP')
    def test_with_password(self, smtp):
        self.smtp_password = "secret"

        action = std.SendEmailAction(
            self.from_addr, self.to_addrs,
            self.smtp_server, self.smtp_password, self.subject, self.body
        )

        action.run()

        smtpmock = smtp.return_value
        calls = [mock.call.ehlo(), mock.call.starttls(), mock.call.ehlo(),
                 mock.call.login(self.from_addr,
                                 self.smtp_password)]

        smtpmock.assert_has_calls(calls)
        self.assertTrue(smtpmock.sendmail.called, "should call sendmail")

    @mock.patch('mistral.actions.std_actions.LOG')
    def test_exception(self, log):
        self.smtp_server = "wrong host"

        action = std.SendEmailAction(
            self.from_addr, self.to_addrs,
            self.smtp_server, None, self.subject, self.body
        )

        try:
            action.run()
        except exc.ActionException:
            pass
        else:
            self.assertFalse("Must throw exception.")
