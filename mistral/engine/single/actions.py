# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from amqplib import client_0_8 as amqp
import requests
from requests import exceptions

from mistral.openstack.common import log as logging
from mistral.openstack.common.apiclient import exceptions as ex

LOG = logging.getLogger(__name__)


class BaseAction(object):
    def __init__(self, action_cfg, task_params, service_parameters=None):
        self.action = action_cfg
        self.task_parameters = task_params
        self.service_parameters = service_parameters

    def run(self, *args, **kwargs):
        pass


class OsloRPCAction(BaseAction):
    def run(self, *args, **kwargs):
        #TODO(nmakhotkin) This one is not finished
        host = self.service_parameters['host']
        port = self.service_parameters.get('port', '5672')
        userid = self.service_parameters['userid']
        password = self.service_parameters['password']
        virtual_host = self.action['parameters']['virtual_host']
        message = self.task_parameters['message']
        routing_key = self.task_parameters.get('routing_key', None)
        exchange = self.action['parameters'].get('exchange')
        queue_name = self.action['parameters']['queue_name']
        # connect to server
        amqp_conn = amqp.Connection(host="%s:%s" % (host, port),
                                    userid=userid,
                                    password=password,
                                    virtual_host=virtual_host)
        channel = amqp_conn.channel()
        # Create a message
        msg = amqp.Message(message)
        # Send message as persistant
        msg.properties["delivery_mode"] = 2
        # Publish the message on the exchange.
        channel.queue_declare(queue=queue_name, durable=True,
                              exclusive=False, auto_delete=False)
        channel.basic_publish(msg, exchange=exchange, routing_key=routing_key)
        channel.basic_consume(queue=queue_name, callback=self.callback)
        channel.wait()
        channel.close()
        amqp_conn.close()

    def callback(self, msg):
        pass


class OpenStackServiceAction(BaseAction):
    #TODO(nmakhotkin) should be implemented
    pass


class RestAPIAction(BaseAction):
    def run(self, *args, **kwargs):
        action_parameters = self.action['parameters']
        url = self.service_parameters['baseUrl']
        url += action_parameters['url']
        headers = kwargs.get('headers')
        headers.update(self.task_parameters.get('headers', {}))
        try:
            response = requests.request(
                method=action_parameters.get('method', 'GET'),
                url=url,
                headers=headers,
                data=self.task_parameters.get("data", {}),
                params=self.task_parameters,
            )
        except exceptions.RequestException as exc:
            raise ex.InternalServerError(exc.message)
        LOG.debug("REST request call to %s" % url)
        return response.text


def get_action(action_type, action_cfg,
               task_params, service_params):
    possible_types = get_possible_service_types()
    actions = [
        RestAPIAction,
        OpenStackServiceAction,
        OsloRPCAction
    ]
    mapping = dict(zip(possible_types, actions))
    return mapping[action_type](action_cfg, task_params, service_params)


def get_possible_service_types():
    return [
        "REST_API",
        "OPENSTACK_SERVICE",
        "OSLO_RPC"
    ]
