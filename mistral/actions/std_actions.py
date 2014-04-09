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

import json
import smtplib
from email.mime.text import MIMEText

import requests

from mistral.openstack.common import log as logging
from mistral.actions import base
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)


class EchoAction(base.Action):
    """Echo action.

    This action just returns a configured value as a result without doing
    anything else. The value of such action implementation is that it
    can be used in development (for testing), demonstration and designing
    of workflows themselves where echo action can play the role of temporary
    stub.
    """

    def __init__(self, output):
        self.output = output

    def run(self):
        LOG.info('Running echo action [output=%s]' % self.output)

        return self.output

    def test(self):
        return 'Echo'


class HTTPAction(base.Action):
    def __init__(self, url, params={}, method="GET", headers={}, body={}):
        self.url = url
        self.params = params
        self.method = method
        self.headers = headers
        self.body = json.dumps(body) if isinstance(body, dict) else body

    def run(self):
        LOG.info("Running HTTP action "
                 "[url=%s, params=%s, method=%s, headers=%s, body=%s]" %
                 (self.method,
                  self.url,
                  self.params,
                  self.headers,
                  self.body))

        try:
            resp = requests.request(self.method,
                                    self.url,
                                    params=self.params,
                                    headers=self.headers,
                                    data=self.body)
        except Exception as e:
            raise exc.ActionException("Failed to send HTTP request: %s" % e)

        LOG.info("HTTP action response:\n%s\n%s" %
                 (resp.status_code, resp.content))

        # TODO: Not sure we need to have this check here in base HTTP action.
        if resp.status_code not in range(200, 307):
            raise exc.ActionException("Received error HTTP code: %s" %
                                      resp.status_code)

        return resp


class MistralHTTPAction(HTTPAction):
    def __init__(self, action_context, url, params, method,
                 headers={}, body={}):
        headers.update({
            'Mistral-Workbook-Name': action_context['workbook_name'],
            'Mistral-Execution-Id': action_context['execution_id'],
            'Mistral-Task-Id': action_context['task_id'],
        })

        super(MistralHTTPAction, self).__init__(url, params, method,
                                                headers, body)


class SendEmailAction(base.Action):
    def __init__(self, params, settings):
        #TODO(dzimine): validate parameters

        # Task invocation parameters.
        self.to = ', '.join(params['to'])
        self.subject = params['subject']
        self.body = params['body']

        # Action provider settings.
        self.smtp_server = settings['smtp_server']
        self.sender = settings['from']
        self.password = settings['password'] \
            if 'password' in settings else None

    def run(self):
        LOG.info("Sending email message "
                 "[from=%s, to=%s, subject=%s, using smtp=%s, body=%s...]" %
                 (self.sender, self.to, self.subject,
                  self.smtp_server, self.body[:128]))

        #TODO(dzimine): handle utf-8, http://stackoverflow.com/a/14506784
        message = MIMEText(self.body)
        message['Subject'] = self.subject
        message['From'] = self.sender
        message['To'] = self.to

        try:
            s = smtplib.SMTP(self.smtp_server)

            if self.password is not None:
                # Sequence to request TLS connection and log in (RFC-2487).
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(self.sender, self.password)

            s.sendmail(from_addr=self.sender,
                       to_addrs=self.to,
                       msg=message.as_string())
        except (smtplib.SMTPException, IOError) as e:
            raise exc.ActionException("Failed to send an email message: %s"
                                      % e)

    def test(self):
        # Just logging the operation since this action is not supposed
        # to return a result.
        LOG.info("Sending email message "
                 "[from=%s, to=%s, subject=%s, using smtp=%s, body=%s...]" %
                 (self.sender, self.to, self.subject,
                  self.smtp_server, self.body[:128]))
