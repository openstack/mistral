# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

#TODO(dzimine):separate actions across different files/modules

import abc
from email.mime.text import MIMEText
import smtplib

from amqplib import client_0_8 as amqp
import requests
import six

from mistral.openstack.common import log as logging
from mistral.engine import expressions as expr
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)


class Action(object):
    status = None

    def __init__(self, action_type, action_name):
        self.type = action_type
        self.name = action_name

    @abc.abstractmethod
    def run(self):
        """Run action logic.

        :return: result of the action. Note that for asynchronous actions
        it will always be None.

        In case if action failed this method must throw a ActionException
        to indicate that.
        """
        pass

    def evaluate_result(self, raw_result):
        result = self.result_helper.copy()
        for k, v in six.iteritems(self.result_helper):
            result[k] = expr.evaluate(v, raw_result)
        return result


class EchoAction(Action):
    """Echo action.

    This action just returns a configured value as a result without doing
    anything else. The value of such action implementation is that it
    can be used in development (for testing), demonstration and designing
    of workflows themselves where echo action can play the role of temporary
    stub.
    """

    def __init__(self, action_type, action_name, output):
        super(EchoAction, self).__init__(action_type, action_name)
        self.output = output

    def run(self):
        return self.output


class RestAction(Action):
    def __init__(self, action_type, action_name, url, params={},
                 method="GET", headers={}, data={}):
        super(RestAction, self).__init__(action_type, action_name)
        self.url = url
        self.params = params
        self.method = method
        self.headers = headers
        self.data = data

    def run(self):
        LOG.info("Sending action HTTP request "
                 "[method=%s, url=%s, params=%s, headers=%s]" %
                 (self.method, self.url, self.params, self.headers))

        try:
            resp = requests.request(self.method,
                                    self.url,
                                    params=self.params,
                                    headers=self.headers,
                                    data=self.data)
        except Exception as e:
            raise exc.ActionException("Failed to send HTTP request: %s" % e)

        LOG.info("Received HTTP response:\n%s\n%s" %
                 (resp.status_code, resp.content))

        self.status = resp.status_code
        if self.result_helper and isinstance(self.result_helper, dict):
            # In case if result_helper exists, we assume response is json.
            return self.evaluate_result(resp.json())
        else:
            try:
                # We prefer to return json than text,
                # but response can contain text also.
                return resp.json()
            except:
                LOG.debug("HTTP response content is not json.")
                return resp.content


class OsloRPCAction(Action):
    def __init__(self, action_type, action_name, host, userid, password,
                 virtual_host, message, routing_key=None, port=5672,
                 exchange=None, queue_name=None):
        super(OsloRPCAction, self).__init__(action_type, action_name)
        self.host = host
        self.port = port
        self.userid = userid
        self.password = password
        self.virtual_host = virtual_host
        self.message = message
        self.routing_key = routing_key
        self.exchange = exchange
        self.queue_name = queue_name

    def run(self):
        #TODO(nmakhotkin) This one is not finished
        LOG.info("Sending action AMQP message "
                 "[host=%s:%s, virtual_host=%s, routing_key=%s, message=%s]" %
                 (self.host, self.port, self.virtual_host,
                  self.routing_key, self.message))
        # connect to server
        amqp_conn = amqp.Connection(host="%s:%s" % (self.host, self.port),
                                    userid=self.userid,
                                    password=self.password,
                                    virtual_host=self.virtual_host)
        channel = amqp_conn.channel()
        # Create a message
        msg = amqp.Message(self.message)
        # Send message as persistant
        msg.properties["delivery_mode"] = 2
        # Publish the message on the exchange.
        channel.queue_declare(queue=self.queue_name, durable=True,
                              exclusive=False, auto_delete=False)
        channel.basic_publish(msg, exchange=self.exchange,
                              routing_key=self.routing_key)
        channel.basic_consume(queue=self.queue_name, callback=self.callback)
        channel.wait()
        channel.close()
        amqp_conn.close()

    def callback(self, msg):
        #TODO (nmakhotkin) set status
        self.status = None


class SendEmailAction(Action):
    def __init__(self, action_type, action_name, params, settings):
        super(SendEmailAction, self).__init__(action_type, action_name)
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
