# Copyright 2015 - Mirantis, Inc.
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

from oslo_config import cfg
import oslo_messaging as messaging

from mistral import exceptions as exc
from mistral import utils


CONF = cfg.CONF
CONF.import_opt('rpc_response_timeout', 'mistral.config')


def get_rpc_info_from_oslo(additional_conf=None):
    transport = messaging.TransportURL.parse(CONF, CONF.transport_url)

    rpc_backend = _get_rpc_backend(transport)

    conf_dict = _get_rpc_info(rpc_backend, transport)

    return utils.merge_dicts(conf_dict, _get_extra_info(additional_conf, ))


def _get_rpc_backend(transport):
    if transport:
        return transport.transport

    return CONF.rpc_backend


def _get_rpc_info(rpc_backend, transport):

    if rpc_backend in ['amqp', 'zmq']:
        return {}
    elif transport and len(transport.hosts) == 1:
        # TODO(ddeja): Handle multiple hosts.
        return _get_rpc_info_from_transport_url(transport, rpc_backend)
    elif rpc_backend in ['rabbit', 'fake']:
        return _get_rabbit_info_from_oslo()
    else:
        raise exc.MistralException(
            'Mistral cannot run with rpc_backend %s' % rpc_backend
        )


def _get_rpc_info_from_transport_url(transport, rpc_backend):
    if rpc_backend in ['rabbit', 'fake']:
        durable_queues = CONF.oslo_messaging_rabbit.amqp_durable_queues
        auto_delete = CONF.oslo_messaging_rabbit.amqp_auto_delete
    else:
        raise exc.MistralException(
            'Mistral cannot run with rpc_backend %s' % rpc_backend
        )

    transport_host = transport.hosts[0]

    return _prepare_conf_dict(
        transport_host.username,
        transport_host.password,
        transport_host.hostname,
        transport_host.port,
        transport.virtual_host or '/',
        durable_queues,
        auto_delete
    )


def _get_rabbit_info_from_oslo():
    return _prepare_conf_dict(
        CONF.oslo_messaging_rabbit.rabbit_userid,
        CONF.oslo_messaging_rabbit.rabbit_password,
        CONF.oslo_messaging_rabbit.rabbit_host,
        CONF.oslo_messaging_rabbit.rabbit_port,
        CONF.oslo_messaging_rabbit.rabbit_virtual_host,
        CONF.oslo_messaging_rabbit.amqp_durable_queues,
        CONF.oslo_messaging_rabbit.amqp_auto_delete,
    )


def _prepare_conf_dict(user_id, password, host, port, virtual_host,
                       durable_queues, auto_delete):
    return {
        'user_id': user_id,
        'password': password,
        'host': host,
        'port': port,
        'virtual_host': virtual_host,
        'durable_queues': durable_queues,
        'auto_delete': auto_delete
    }


def _get_extra_info(additional_conf):
    return {
        'exchange': CONF.control_exchange,
        'topic': additional_conf.topic,
        'server_id': additional_conf.host,
        'timeout': CONF.rpc_response_timeout
    }
