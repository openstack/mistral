# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
# Copyright 2014 - StackStorm, Inc.
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

from email import header
from email.mime import text

import json
import requests
import six
import smtplib
import time

from mistral.actions import base
from mistral import exceptions as exc
from mistral.utils import javascript
from mistral.utils import ssh_utils
from mistral.workflow import utils as wf_utils
from oslo_log import log as logging

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


class NoOpAction(base.Action):
    """No-operation action.

    This action does nothing. It can be mostly useful for testing and
    debugging purposes.
    """
    def __init__(self):
        pass

    def run(self):
        LOG.info('Running no-op action')

        return None

    def test(self):
        return None


class AsyncNoOpAction(NoOpAction):
    """Asynchronous no-operation action."""
    def is_sync(self):
        return False


class FailAction(base.Action):
    """'Always fail' action.

    This action just always throws an instance of ActionException.
    This behavior is useful in a number of cases, especially if we need to
    test a scenario where some of workflow tasks fail.
    """

    def __init__(self):
        pass

    def run(self):
        LOG.info('Running fail action.')

        raise exc.ActionException('Fail action expected exception.')

    def test(self):
        raise exc.ActionException('Fail action expected exception.')


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
    :param verify: (optional) if ``True``, the SSL cert will be verified.
        A CA_BUNDLE path can also be provided.
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
                 proxies=None,
                 verify=None):

        if auth and len(auth.split(':')) == 2:
            self.auth = (auth.split(':')[0], auth.split(':')[1])
        else:
            self.auth = auth

        if isinstance(headers, dict):
            for key, val in headers.items():
                if isinstance(val, (six.integer_types, float)):
                    headers[key] = str(val)

        self.url = url
        self.method = method
        self.params = params
        self.body = json.dumps(body) if isinstance(body, dict) else body
        self.headers = headers
        self.cookies = cookies
        self.timeout = timeout
        self.allow_redirects = allow_redirects
        self.proxies = proxies
        self.verify = verify

    def run(self):
        LOG.info("Running HTTP action "
                 "[url=%s, method=%s, params=%s, body=%s, headers=%s,"
                 " cookies=%s, auth=%s, timeout=%s, allow_redirects=%s,"
                 " proxies=%s, verify=%s]" %
                 (self.url,
                  self.method,
                  self.params,
                  self.body,
                  self.headers,
                  self.cookies,
                  self.auth,
                  self.timeout,
                  self.allow_redirects,
                  self.proxies,
                  self.verify))

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
                proxies=self.proxies,
                verify=self.verify
            )
        except Exception as e:
            raise exc.ActionException("Failed to send HTTP request: %s" % e)

        LOG.info(
            "HTTP action response:\n%s\n%s" % (resp.status_code, resp.content)
        )

        # Represent important resp data as a dictionary.
        try:
            content = resp.json()
        except Exception as e:
            LOG.debug("HTTP action response is not json.")
            content = resp.content

        _result = {
            'content': content,
            'status': resp.status_code,
            'headers': dict(resp.headers.items()),
            'url': resp.url,
            'history': resp.history,
            'encoding': resp.encoding,
            'reason': resp.reason,
            'cookies': dict(resp.cookies.items()),
            'elapsed': resp.elapsed.total_seconds()
        }

        if resp.status_code not in range(200, 307):
            return wf_utils.Result(error=_result)

        return _result

    def test(self):
        # TODO(rakhmerov): Implement.
        return None


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
                 proxies=None,
                 verify=None):

        actx = action_context

        headers = headers or {}
        headers.update({
            'Mistral-Workflow-Name': actx.get('workflow_name'),
            'Mistral-Workflow-Execution-Id': actx.get('workflow_execution_id'),
            'Mistral-Task-Id': actx.get('task_id'),
            'Mistral-Action-Execution-Id': actx.get('action_execution_id'),
            'Mistral-Callback-URL': actx.get('callback_url'),
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
            verify,
        )

    def is_sync(self):
        return False

    def test(self):
        return None


class SendEmailAction(base.Action):
    def __init__(self, from_addr, to_addrs, smtp_server,
                 smtp_password, subject=None, body=None):
        # TODO(dzimine): validate parameters

        # Task invocation parameters.
        self.to = to_addrs
        self.subject = subject or "<No subject>"
        self.body = body

        # Action provider settings.
        self.smtp_server = smtp_server
        self.sender = from_addr
        self.password = smtp_password

    def run(self):
        LOG.info("Sending email message "
                 "[from=%s, to=%s, subject=%s, using smtp=%s, body=%s...]" %
                 (self.sender, self.to, self.subject,
                  self.smtp_server, self.body[:128]))

        message = text.MIMEText(self.body, _charset='utf-8')
        message['Subject'] = header.Header(self.subject, 'utf-8')
        message['From'] = self.sender
        message['To'] = ', '.join(self.to)

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
    """Runs Secure Shell (SSH) command on provided single or multiple hosts.

    It is allowed to provide either a single host or a list of hosts in
    action parameter 'host'. In case of a single host the action result
    will be a single value, otherwise a list of results provided in the
    same order as provided hosts.
    """
    @property
    def _execute_cmd_method(self):
        return ssh_utils.execute_command

    def __init__(self, cmd, host, username,
                 password=None, private_key_filename=None):
        self.cmd = cmd
        self.host = host
        self.username = username
        self.password = password
        self.private_key_filename = private_key_filename

        self.params = {
            'cmd': self.cmd,
            'host': self.host,
            'username': self.username,
            'password': self.password,
            'private_key_filename': self.private_key_filename
        }

    def run(self):
        def raise_exc(parent_exc=None):
            message = ("Failed to execute ssh cmd "
                       "'%s' on %s" % (self.cmd, self.host))
            if parent_exc:
                message += "\nException: %s" % str(parent_exc)
            raise exc.ActionException(message)

        try:
            results = []

            if not isinstance(self.host, list):
                self.host = [self.host]

            for host_name in self.host:
                self.params['host'] = host_name

                status_code, result = self._execute_cmd_method(**self.params)

                if status_code > 0:
                    return raise_exc()
                else:
                    results.append(result)

            if len(results) > 1:
                return results

            return result
        except Exception as e:
            return raise_exc(parent_exc=e)

    def test(self):
        # TODO(rakhmerov): Implement.
        return None


class SSHProxiedAction(SSHAction):
    @property
    def _execute_cmd_method(self):
        return ssh_utils.execute_command_via_gateway

    def __init__(self, cmd, host, username, private_key_filename,
                 gateway_host, gateway_username=None,
                 password=None, proxy_command=None):
        super(SSHProxiedAction, self).__init__(
            cmd,
            host,
            username,
            password,
            private_key_filename
        )

        self.gateway_host = gateway_host
        self.gateway_username = gateway_username

        self.params.update(
            {
                'gateway_host': gateway_host,
                'gateway_username': gateway_username,
                'proxy_command': proxy_command
            }
        )


class JavaScriptAction(base.Action):
    """Evaluates given JavaScript.

    """
    def __init__(self, script, context=None):
        self.script = script
        self.context = context

    def run(self):
        try:
            script = """function f() {
                %s
            }
            f()
            """ % self.script
            return javascript.evaluate(script, self.context)
        except Exception as e:
            raise exc.ActionException("JavaScriptAction failed: %s" % str(e))

    def test(self):
        return self.script


class SleepAction(base.Action):
    """Sleep action.

    This action sleeps for given amount of seconds. It can be mostly useful
    for testing and debugging purposes.
    """
    def __init__(self, seconds=1):
        try:
            self._seconds = int(seconds)
            self._seconds = 0 if self._seconds < 0 else self._seconds
        except ValueError:
            self._seconds = 0

    def run(self):
        LOG.info('Running sleep action [seconds=%s]' % self._seconds)

        time.sleep(self._seconds)

        return None

    def test(self):
        time.sleep(1)

        return None
