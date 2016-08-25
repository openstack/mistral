# Copyright 2015 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

import kombu
from kombu import serialization

from mistral.utils import serializers


class Base(object):
    """Base class for Client and Server."""

    @staticmethod
    def _make_connection(amqp_host, amqp_port, amqp_user, amqp_password,
                         amqp_vhost):
        """Create connection.

        This method creates object representing the connection to RabbitMQ.

        :param amqp_host: Address of RabbitMQ server.
        :param amqp_user: Username for connecting to RabbitMQ.
        :param amqp_password: Password matching the given username.
        :param amqp_vhost: Virtual host to connect to.
        :param amqp_port: Port of RabbitMQ server.
        :return: New connection to RabbitMQ.
        """
        return kombu.BrokerConnection(
            hostname=amqp_host,
            userid=amqp_user,
            password=amqp_password,
            virtual_host=amqp_vhost,
            port=amqp_port
        )

    @staticmethod
    def _make_exchange(name, durable=False, auto_delete=True,
                       exchange_type='topic'):
        """Make named exchange.

        This method creates object representing exchange on RabbitMQ. It would
        create a new exchange if exchange with given name don't exists.

        :param name: Name of the exchange.
        :param durable: If set to True, messages on this exchange would be
                        store on disk - therefore can be retrieve after
                        failure.
        :param auto_delete: If set to True, exchange would be automatically
                            deleted when none is connected.
        :param exchange_type: Type of the exchange. Can be one of 'direct',
                              'topic', 'fanout', 'headers'. See Kombu docs for
                              further details.
        :return: Kombu exchange object.
        """
        return kombu.Exchange(
            name=name,
            type=exchange_type,
            durable=durable,
            auto_delete=auto_delete
        )

    @staticmethod
    def _make_queue(name, exchange, routing_key='',
                    durable=False, auto_delete=True, **kwargs):
        """Make named queue for a given exchange.

        This method creates object representing queue in RabbitMQ. It would
        create a new queue if queue with given name don't exists.

        :param name: Name of the queue
        :param exchange: Kombu Exchange object (can be created using
                         _make_exchange).
        :param routing_key: Routing key for queue. It behaves differently
                            depending the exchange type. See Kombu docs for
                            further details.
        :param durable: If set to True, messages on this queue would be
                        store on disk - therefore can be retrieve after
                        failure.
        :param auto_delete: If set to True, queue would be automatically
                            deleted when none is connected.
        :param kwargs: See kombu documentation for all parameters than may be
                       may be passed to Queue.
        :return: Kombu Queue object.
        """
        return kombu.Queue(
            name=name,
            routing_key=routing_key,
            exchange=exchange,
            durable=durable,
            auto_delete=auto_delete,
            **kwargs
        )

    @staticmethod
    def _register_mistral_serialization():
        """Adds mistral serializer to available serializers in kombu.

        :return: None
        """
        serialization.register(
            'mistral_serialization',
            encoder=serializers.KombuSerializer.serialize,
            decoder=serializers.KombuSerializer.deserialize,
            content_type='application/json'
        )
