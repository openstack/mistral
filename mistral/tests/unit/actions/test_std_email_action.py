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
import socket
from unittest import mock

from mistral.actions import std_actions as std
from mistral import exceptions as exc
from mistral.tests.unit import base


class SendEmailActionTest(base.BaseTest):

    def setUp(self):
        super(SendEmailActionTest, self).setUp()
        self.to_addrs = ["dz@example.com", "deg@example.com",
                         "xyz@example.com"]
        self.reply_to = ['reply-to@example.com']
        self.cc_addrs = ['copy@example.com']
        self.bcc_addrs = ['hidden_copy@example.com']
        self.subject = "Multi word subject с русскими буквами"
        self.body = "short multiline\nbody\nc русскими буквами"
        self.html_body = '<html><body><b>HTML</b> body</body></html>'

        self.smtp_server = 'mail.example.com:25'
        self.from_addr = "bot@example.com"

        self.to_addrs_str = ", ".join(self.to_addrs)
        self.reply_to_str = ", ".join(self.reply_to)
        self.ctx = mock.Mock()

        gai = mock.patch.object(
            socket,
            'getaddrinfo',
            return_value=[
                (socket.AF_INET, socket.SOCK_STREAM, 6, '',
                 ('93.184.216.34', 25))
            ]
        )
        self.getaddrinfo = gai.start()
        self.addCleanup(gai.stop)

    @mock.patch('smtplib.SMTP')
    def test_send_email(self, smtp):
        action = std.SendEmailAction(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            smtp_server=self.smtp_server,
            smtp_password=None,
            subject=self.subject,
            body=self.body
        )

        action.run(self.ctx)

        smtp.assert_called_once_with('mail.example.com', 25, timeout=30)

        sendmail = smtp.return_value.sendmail

        self.assertTrue(sendmail.called, "should call sendmail")
        self.assertEqual(
            self.from_addr, sendmail.call_args[1]['from_addr'])
        self.assertEqual(
            self.to_addrs, sendmail.call_args[1]['to_addrs'])

        message = parser.Parser().parsestr(sendmail.call_args[1]['msg'])

        self.assertEqual(self.from_addr, message['from'])
        self.assertEqual(self.to_addrs_str, message['to'])
        self.assertEqual(
            self.subject,
            decode_header(message['subject'])[0][0].decode('utf-8')
        )

        self.assertEqual(
            self.body,
            base64.b64decode(message.get_payload()).decode('utf-8')
        )

    @mock.patch('smtplib.SMTP')
    def test_send_email_with_cc(self, smtp):
        to_addrs = self.cc_addrs + self.to_addrs
        cc_addrs_str = ", ".join(self.cc_addrs)

        action = std.SendEmailAction(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            cc_addrs=self.cc_addrs,
            smtp_server=self.smtp_server,
            smtp_password=None,
            subject=self.subject,
            body=self.body
        )

        action.run(self.ctx)

        smtp.assert_called_once_with('mail.example.com', 25, timeout=30)

        sendmail = smtp.return_value.sendmail

        self.assertTrue(sendmail.called, "should call sendmail")
        self.assertEqual(
            self.from_addr, sendmail.call_args[1]['from_addr'])
        self.assertEqual(
            to_addrs, sendmail.call_args[1]['to_addrs'])

        message = parser.Parser().parsestr(sendmail.call_args[1]['msg'])

        self.assertEqual(self.from_addr, message['from'])
        self.assertEqual(self.to_addrs_str, message['to'])
        self.assertEqual(cc_addrs_str, message['cc'])

    @mock.patch('smtplib.SMTP')
    def test_send_email_with_bcc(self, smtp):
        to_addrs = self.bcc_addrs + self.to_addrs
        action = std.SendEmailAction(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            bcc_addrs=self.bcc_addrs,
            smtp_server=self.smtp_server,
            smtp_password=None,
            subject=self.subject,
            body=self.body
        )

        action.run(self.ctx)

        smtp.assert_called_once_with('mail.example.com', 25, timeout=30)

        sendmail = smtp.return_value.sendmail

        self.assertTrue(sendmail.called, "should call sendmail")
        self.assertEqual(
            self.from_addr, sendmail.call_args[1]['from_addr'])
        self.assertEqual(
            to_addrs, sendmail.call_args[1]['to_addrs'])

        message = parser.Parser().parsestr(sendmail.call_args[1]['msg'])

        self.assertEqual(self.from_addr, message['from'])
        self.assertEqual(self.to_addrs_str, message['to'])

    @mock.patch('smtplib.SMTP')
    def test_send_email_with_reply_to(self, smtp):
        action = std.SendEmailAction(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            reply_to=self.reply_to,
            bcc_addrs=self.bcc_addrs,
            smtp_server=self.smtp_server,
            smtp_password=None,
            subject=self.subject,
            body=self.body
        )

        action.run(self.ctx)

        smtp.assert_called_once_with('mail.example.com', 25, timeout=30)

        sendmail = smtp.return_value.sendmail

        self.assertTrue(sendmail.called, "should call sendmail")
        self.assertEqual(
            self.from_addr, sendmail.call_args[1]['from_addr'])

        message = parser.Parser().parsestr(sendmail.call_args[1]['msg'])

        self.assertEqual(self.from_addr, message['from'])
        self.assertEqual(self.to_addrs_str, message['to'])
        self.assertEqual(self.reply_to_str, message['reply-to'])

    @mock.patch('smtplib.SMTP')
    def test_send_email_html(self, smtp):
        action = std.SendEmailAction(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            smtp_server=self.smtp_server,
            smtp_password=None,
            subject=self.subject,
            body=self.body,
            html_body=self.html_body
        )

        action.run(self.ctx)

        smtp.assert_called_once_with('mail.example.com', 25, timeout=30)

        sendmail = smtp.return_value.sendmail

        self.assertTrue(sendmail.called, "should call sendmail")
        self.assertEqual(
            self.from_addr, sendmail.call_args[1]['from_addr'])
        self.assertEqual(
            self.to_addrs, sendmail.call_args[1]['to_addrs'])

        message = parser.Parser().parsestr(sendmail.call_args[1]['msg'])

        self.assertEqual(self.from_addr, message['from'])
        self.assertEqual(self.to_addrs_str, message['to'])
        self.assertEqual(
            self.subject,
            decode_header(message['subject'])[0][0].decode('utf-8')
        )
        body_payload = message.get_payload(0).get_payload()
        self.assertEqual(
            self.body,
            base64.b64decode(body_payload).decode('utf-8')
        )
        html_body_payload = message.get_payload(1).get_payload()
        self.assertEqual(
            self.html_body,
            base64.b64decode(html_body_payload).decode('utf-8')
        )

    @mock.patch('smtplib.SMTP')
    def test_with_password(self, smtp):
        self.smtp_password = "secret"

        action = std.SendEmailAction(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            smtp_server=self.smtp_server,
            smtp_password=self.smtp_password,
            subject=self.subject,
            body=self.body
        )

        action.run(self.ctx)

        smtpmock = smtp.return_value
        calls = [mock.call.ehlo(), mock.call.starttls(), mock.call.ehlo(),
                 mock.call.login(self.from_addr,
                                 self.smtp_password)]

        smtpmock.assert_has_calls(calls)
        self.assertTrue(smtpmock.sendmail.called, "should call sendmail")

    @mock.patch('mistral.actions.std_actions.LOG')
    def test_exception(self, log):
        self.smtp_server = "wrong host"
        self.getaddrinfo.side_effect = socket.gaierror

        action = std.SendEmailAction(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            smtp_server=self.smtp_server,
            smtp_password=None,
            subject=self.subject,
            body=self.body
        )

        try:
            action.run(self.ctx)
        except exc.ActionException:
            pass
        else:
            self.assertFalse("Must throw exception.")

    def _action(self, **kwargs):
        params = dict(
            from_addr=self.from_addr,
            to_addrs=self.to_addrs,
            smtp_server=self.smtp_server,
            smtp_password=None,
            subject=self.subject,
            body=self.body
        )
        params.update(kwargs)

        return std.SendEmailAction(**params)

    @mock.patch('smtplib.SMTP')
    def test_default_port(self, smtp):
        self._action(smtp_server='mail.example.com').run(self.ctx)

        smtp.assert_called_once_with('mail.example.com', 25, timeout=30)

    @mock.patch('smtplib.SMTP')
    def test_timeout_disabled(self, smtp):
        self.override_config('timeout', 0, group='action_std_email')

        self._action().run(self.ctx)

        smtp.assert_called_once_with('mail.example.com', 25)

    @mock.patch('smtplib.SMTP')
    def test_invalid_port(self, smtp):
        self.assertRaises(
            exc.ActionException,
            self._action(smtp_server='mail.example.com:smtp').run,
            self.ctx
        )
        smtp.assert_not_called()

    @mock.patch('smtplib.SMTP')
    def test_denied_address(self, smtp):
        for ip in ('127.0.0.1', '169.254.169.254'):
            self.getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 25))
            ]

            self.assertRaises(
                exc.UrlNotAllowedException,
                self._action(smtp_server='%s:22' % ip).run,
                self.ctx
            )

        smtp.assert_not_called()

    @mock.patch('smtplib.SMTP')
    def test_denied_cidrs_emptied(self, smtp):
        self.override_config('denied_cidrs', [], group='action_std_email')
        self.getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 25))
        ]

        self._action(smtp_server='localhost').run(self.ctx)

        smtp.assert_called_once_with('localhost', 25, timeout=30)

    @mock.patch('smtplib.SMTP')
    def test_allowed_hosts(self, smtp):
        self.override_config(
            'allowed_hosts',
            ['mail.example.com'],
            group='action_std_email'
        )

        self._action().run(self.ctx)

        self.assertRaises(
            exc.UrlNotAllowedException,
            self._action(smtp_server='other.example.com:25').run,
            self.ctx
        )
        smtp.assert_called_once_with('mail.example.com', 25, timeout=30)

    @mock.patch('smtplib.SMTP')
    def test_error_is_not_leaked(self, smtp):
        smtp.side_effect = ConnectionRefusedError(111, 'Connection refused')

        e = self.assertRaises(
            exc.ActionException,
            self._action(smtp_server='mail.example.com:2222').run,
            self.ctx
        )

        self.assertEqual('Failed to send an email message.', str(e))
