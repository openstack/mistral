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
from email.mime import multipart
from email.mime import text
import json
import smtplib
import time

from oslo_log import log as logging
import requests
import six

from mistral import exceptions as exc
from mistral.utils import javascript
from mistral.utils import ssh_utils
from mistral_lib import actions

LOG = logging.getLogger(__name__)


class EchoAction(actions.Action):
    """Echo action.

    This action just returns a configured value as a result without doing
    anything else. The value of such action implementation is that it
    can be used in development (for testing), demonstration and designing
    of workflows themselves where echo action can play the role of temporary
    stub.
    """

    def __init__(self, output):
        super(EchoAction, self).__init__()

        self.output = output

    def run(self, context):
        LOG.info('Running echo action [output=%s]', self.output)

        return self.output

    def test(self, context):
        return 'Echo'


class NoOpAction(actions.Action):
    """No-operation action.

    This action does nothing. It can be mostly useful for testing and
    debugging purposes.
    """
    def run(self, context):
        LOG.info('Running no-op action')

        return None

    def test(self, context):
        return None


class AsyncNoOpAction(NoOpAction):
    """Asynchronous no-operation action."""
    def is_sync(self):
        return False


class FailAction(actions.Action):
    """'Always fail' action.

    If you pass the `error_data` parameter, this action will be failed and
    return this data as error data. Otherwise, the action just throws an
    instance of ActionException.

    This behavior is useful in a number of cases, especially if we need to
    test a scenario where some of workflow tasks fail.

    :param error_data: Action will be failed with this data
    """

    def __init__(self, error_data=None):
        super(FailAction, self).__init__()

        self.error_data = error_data

    def run(self, context):
        LOG.info('Running fail action.')

        if self.error_data:
            return actions.Result(error=self.error_data)

        raise exc.ActionException('Fail action expected exception.')

    def test(self, context):
        if self.error_data:
            return actions.Result(error=self.error_data)

        raise exc.ActionException('Fail action expected exception.')


class HTTPAction(actions.Action):
    """HTTP action.

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
        super(HTTPAction, self).__init__()

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

    def run(self, context):
        LOG.info(
            "Running HTTP action "
            "[url=%s, method=%s, params=%s, body=%s, headers=%s,"
            " cookies=%s, auth=%s, timeout=%s, allow_redirects=%s,"
            " proxies=%s, verify=%s]",
            self.url,
            self.method,
            self.params,
            self.body,
            self.headers,
            self.cookies,
            self.auth,
            self.timeout,
            self.allow_redirects,
            self.proxies,
            self.verify
        )

        try:
            url_data = six.moves.urllib.parse.urlsplit(self.url)
            if 'https' == url_data.scheme:
                action_verify = self.verify
            else:
                action_verify = None

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
                verify=action_verify
            )
        except Exception as e:
            LOG.exception(
                "Failed to send HTTP request for action execution: %s",
                context.execution.action_execution_id
            )
            raise exc.ActionException("Failed to send HTTP request: %s" % e)

        LOG.info(
            "HTTP action response:\n%s\n%s",
            resp.status_code,
            resp.content
        )

        # Represent important resp data as a dictionary.
        try:
            content = resp.json(encoding=resp.encoding)
        except Exception as e:
            LOG.debug("HTTP action response is not json.")
            content = resp.content
            if content and resp.encoding not in (None, 'utf-8'):
                content = content.decode(resp.encoding).encode('utf-8')

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
            return actions.Result(error=_result)

        return _result

    def test(self, context):
        # TODO(rakhmerov): Implement.
        return None


class MistralHTTPAction(HTTPAction):

    def run(self, context):
        self.headers = self.headers or {}

        exec_ctx = context.execution
        self.headers.update({
            'Mistral-Workflow-Name': exec_ctx.workflow_name,
            'Mistral-Workflow-Execution-Id': exec_ctx.workflow_execution_id,
            'Mistral-Task-Id': exec_ctx.task_execution_id,
            'Mistral-Action-Execution-Id': exec_ctx.action_execution_id,
            'Mistral-Callback-URL': exec_ctx.callback_url,
        })

        return super(MistralHTTPAction, self).run(context)

    def is_sync(self):
        return False

    def test(self, context):
        return None


class SendEmailAction(actions.Action):
    def __init__(self, from_addr, to_addrs, smtp_server, cc_addrs=None,
                 bcc_addrs=None, smtp_password=None, subject=None, body=None,
                 html_body=None):
        super(SendEmailAction, self).__init__()
        # TODO(dzimine): validate parameters

        # Task invocation parameters.
        self.to = to_addrs
        self.cc = cc_addrs or []
        self.bcc = bcc_addrs or []
        self.subject = subject or "<No subject>"
        self.body = body or "<No body>"
        self.html_body = html_body

        # Action provider settings.
        self.smtp_server = smtp_server
        self.sender = from_addr
        self.password = smtp_password

    def run(self, context):
        LOG.info(
            "Sending email message "
            "[from=%s, to=%s, cc=%s, bcc=%s, subject=%s, using smtp=%s, "
            "body=%s...]",
            self.sender,
            self.to,
            self.cc,
            self.bcc,
            self.subject,
            self.smtp_server,
            self.body[:128]
        )
        if not self.html_body:
            message = text.MIMEText(self.body, _charset='utf-8')
        else:
            message = multipart.MIMEMultipart('alternative')
            message.attach(text.MIMEText(self.body,
                                         'plain',
                                         _charset='utf-8'))
            message.attach(text.MIMEText(self.html_body,
                                         'html',
                                         _charset='utf-8'))
        message['Subject'] = header.Header(self.subject, 'utf-8')
        message['From'] = self.sender
        message['To'] = ', '.join(self.to)

        if self.cc:
            message['cc'] = ', '.join(self.cc)

        rcpt = self.cc + self.bcc + self.to

        try:
            s = smtplib.SMTP(self.smtp_server)

            if self.password is not None:
                # Sequence to request TLS connection and log in (RFC-2487).
                s.ehlo()
                s.starttls()
                s.ehlo()
                s.login(self.sender, self.password)

            s.sendmail(from_addr=self.sender,
                       to_addrs=rcpt,
                       msg=message.as_string())
        except (smtplib.SMTPException, IOError) as e:
            raise exc.ActionException("Failed to send an email message: %s"
                                      % e)

    def test(self, context):
        # Just logging the operation since this action is not supposed
        # to return a result.
        LOG.info(
            "Sending email message "
            "[from=%s, to=%s, cc=%s, bcc=%s, subject=%s, using smtp=%s, "
            "body=%s...]",
            self.sender,
            self.to,
            self.cc,
            self.bcc,
            self.subject,
            self.smtp_server,
            self.body[:128]
        )


class SSHAction(actions.Action):
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
                 password="", private_key_filename=None):
        super(SSHAction, self).__init__()

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

    def run(self, context):
        def raise_exc(parent_exc=None):
            message = ("Failed to execute ssh cmd "
                       "'%s' on %s" % (self.cmd, self.host))
            # We suppress the actual parent error messages in favor of
            # more generic ones as we might be leaking information to the CLI
            if parent_exc:
                # The full error message needs to be logged regardless
                LOG.exception(message + " Exception: %s", str(parent_exc))
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

    def test(self, context):
        return json.dumps(self.params)


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


class JavaScriptAction(actions.Action):
    """Evaluates given JavaScript.

    """

    def __init__(self, script, context=None):
        """Context here refers to a javasctript context

        Not the usual mistral context. That is passed during the run method
        """
        super(JavaScriptAction, self).__init__()

        self.script = script
        self.js_context = context

    def run(self, context):
        try:
            script = """function f() {
                %s
            }
            f()
            """ % self.script
            return javascript.evaluate(script, self.js_context)
        except Exception as e:
            raise exc.ActionException("JavaScriptAction failed: %s" % str(e))

    def test(self, context):
        return self.script


class SleepAction(actions.Action):
    """Sleep action.

    This action sleeps for given amount of seconds. It can be mostly useful
    for testing and debugging purposes.
    """
    def __init__(self, seconds=1):
        super(SleepAction, self).__init__()

        try:
            self._seconds = int(seconds)
            self._seconds = 0 if self._seconds < 0 else self._seconds
        except ValueError:
            self._seconds = 0

    def run(self, context):
        LOG.info('Running sleep action [seconds=%s]', self._seconds)

        time.sleep(self._seconds)

        return None

    def test(self, context):
        time.sleep(1)

        return None


class TestDictAction(actions.Action):
    """Generates test dict."""

    def __init__(self, size=0, key_prefix='', val=''):
        super(TestDictAction, self).__init__()

        self.size = size
        self.key_prefix = key_prefix
        self.val = val

    def run(self, context):
        LOG.info(
            'Running test_dict action [size=%s, key_prefix=%s, val=%s]',
            self.size,
            self.key_prefix,
            self.val
        )

        res = {}

        for i in range(self.size):
            res['%s%s' % (self.key_prefix, i)] = self.val

        return res

    def test(self, context):
        return {}
