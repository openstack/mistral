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

from email.mime import text
import json
import requests
import smtplib

from mistral.actions import base
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.utils import ssh_utils


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
    """Constructs an HTTP action.

    :param url: URL for the new HTTP request.
    :param method: (optional, 'GET' by default) method for the new HTTP
        request.
    :param params: (optional) Dictionary or bytes to be sent in the
        query string for the HTTP request.
    :param body: (optional) Dictionary, bytes, or file-like object to send
        in the body of the HTTP request.
    :param headers: (optional) Dictionary of HTTP Headers to send with
        the HTTP request.
    :param cookies: (optional) Dict or CookieJar object to send with
        the HTTP request.
    :param auth: (optional) Auth tuple to enable Basic/Digest/Custom
        HTTP Auth.
    :param timeout: (optional) Float describing the timeout of the request
        in seconds.
    :param allow_redirects: (optional) Boolean. Set to True if POST/PUT/DELETE
        redirect following is allowed.
    :param proxies: (optional) Dictionary mapping protocol to the URL of
        the proxy.
    """

    def __init__(self,
                 url,
                 method="GET",
                 params=None,
                 body=None,
                 headers=None,
                 cookies=None,
                 auth=None,
                 timeout=None,
                 allow_redirects=None,
                 proxies=None):
        self.url = url
        self.method = method
        self.params = params
        self.body = json.dumps(body) if isinstance(body, dict) else body
        self.headers = headers
        self.cookies = cookies
        self.auth = auth
        self.timeout = timeout
        self.allow_redirects = allow_redirects
        self.proxies = proxies

    def run(self):
        LOG.info("Running HTTP action "
                 "[url=%s, method=%s, params=%s, body=%s, headers=%s,"
                 " cookies=%s, auth=%s, timeout=%s, allow_redirects=%s,"
                 " proxies=%s]" %
                 (self.url,
                  self.method,
                  self.params,
                  self.body,
                  self.headers,
                  self.cookies,
                  self.auth,
                  self.timeout,
                  self.allow_redirects,
                  self.proxies))

        try:
            resp = requests.request(
                self.method,
                self.url,
                params=self.params,
                data=self.body,
                headers=self.headers,
                cookies=self.cookies,
                auth=self.auth,
                timeout=self.timeout,
                allow_redirects=self.allow_redirects,
                proxies=self.proxies
            )
        except Exception as e:
            raise exc.ActionException("Failed to send HTTP request: %s" % e)

        LOG.info("HTTP action response:\n%s\n%s" %
                 (resp.status_code, resp.content))

        # TODO(everyone): Not sure we need to have this check here in base HTTP
        #                 action.
        if resp.status_code not in range(200, 307):
            raise exc.ActionException("Received error HTTP code: %s" %
                                      resp.status_code)

        # Construct all important resp data in readable structure.
        headers = dict(resp.headers.items())
        status = resp.status_code
        try:
            content = resp.json()
        except Exception as e:
            LOG.debug("HTTP action response is not json.")
            content = resp.content

        return {'content': content, 'headers': headers, 'status': status}


class MistralHTTPAction(HTTPAction):
    def __init__(self,
                 action_context,
                 url,
                 method="GET",
                 params=None,
                 body=None,
                 headers=None,
                 cookies=None,
                 auth=None,
                 timeout=None,
                 allow_redirects=None,
                 proxies=None):
        headers.update({
            'Mistral-Workbook-Name': action_context['workbook_name'],
            'Mistral-Execution-Id': action_context['execution_id'],
            'Mistral-Task-Id': action_context['task_id'],
        })

        super(MistralHTTPAction, self).__init__(
            url,
            method,
            params,
            body,
            headers,
            cookies,
            auth,
            timeout,
            allow_redirects,
            proxies,
        )

    def is_sync(self):
        return False


class SendEmailAction(base.Action):
    def __init__(self, params, settings):
        # TODO(dzimine): validate parameters

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

        # TODO(dzimine): handle utf-8, http://stackoverflow.com/a/14506784
        message = text.MIMEText(self.body)
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


class SSHAction(base.Action):
    def __init__(self, cmd, host, username, password):
        self.cmd = cmd
        self.host = host
        self.username = username
        self.password = password

    def run(self):
        def raise_exc(parent_exc=None):
            message = ("Failed to execute ssh cmd "
                       "'%s' on %s" % (self.cmd, self.host))
            if parent_exc:
                message += "\nException: %s" % str(parent_exc)
            raise exc.ActionException(message)

        try:
            status_code, result = ssh_utils.execute_command(self.cmd,
                                                            self.host,
                                                            self.username,
                                                            self.password)
            if status_code > 0:
                return raise_exc()

            return result
        except Exception as e:
            return raise_exc(parent_exc=e)


class AdHocAction(base.Action):
    def __init__(self, action_context,
                 base_action_cls, action_spec, **params):
        self.base_action_cls = base_action_cls
        self.action_spec = action_spec

        base_params = self._convert_params(params)

        if action_context:
            base_params['action_context'] = action_context

        self.base_action = base_action_cls(**base_params)

    def _convert_params(self, params):
        base_params_spec = self.action_spec.base_parameters

        if not base_params_spec:
            return {}

        return expr.evaluate_recursively(base_params_spec, params)

    def _convert_result(self, result):
        transformer = self.action_spec.output

        if not transformer:
            return result

        # Use base action result as a context for evaluating expressions.
        return expr.evaluate_recursively(transformer, result)

    def is_sync(self):
        return self.base_action.is_sync()

    def run(self):
        try:
            return self._convert_result(self.base_action.run())
        except Exception as e:
            raise exc.ActionException("Failed to convert result in action %s,"
                                      "[Exception = %s"
                                      % (self.action_spec.name, e))

    def test(self):
        return self._convert_result(self.base_action.test())
