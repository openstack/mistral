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

import socket
import threading

import kombu
from oslo_log import log as logging

from mistral import context as auth_ctx
from mistral.engine.rpc_backend import base as rpc_base
from mistral.engine.rpc_backend.kombu import base as kombu_base
from mistral import exceptions as exc


LOG = logging.getLogger(__name__)


class KombuRPCServer(rpc_base.RPCServer, kombu_base.Base):
    def __init__(self, conf):
        super(KombuRPCServer, self).__init__(conf)

        self._register_mistral_serialization()

        self.exchange = conf.get('exchange', '')
        self.user_id = conf.get('user_id', 'guest')
        self.password = conf.get('password', 'guest')
        self.topic = conf.get('topic', 'mistral')
        self.server_id = conf.get('server_id', '')
        self.host = conf.get('host', 'localhost')
        self.port = conf.get('port', 5672)
        self.virtual_host = conf.get('virtual_host', '/')
        self.durable_queue = conf.get('durable_queues', False)
        self.auto_delete = conf.get('auto_delete', False)
        self.routing_key = self.topic
        self.channel = None
        self.conn = None
        self._running = threading.Event()
        self.endpoints = []

    @property
    def is_running(self):
        """Return whether server is running."""
        return self._running.is_set()

    def run(self, executor='blocking'):
        """Start the server."""
        self.conn = self._make_connection(
            self.host,
            self.port,
            self.user_id,
            self.password,
            self.virtual_host,
        )
        LOG.info("Connected to AMQP at %s:%s" % (self.host, self.port))

        try:
            conn = kombu.connections[self.conn].acquire(block=True)
            exchange = self._make_exchange(
                self.exchange,
                durable=self.durable_queue,
                auto_delete=self.auto_delete
            )
            queue = self._make_queue(
                self.topic,
                exchange,
                routing_key=self.routing_key,
                durable=self.durable_queue,
                auto_delete=self.auto_delete
            )
            with conn.Consumer(
                    queues=queue,
                    callbacks=[self._on_message_safe],
            ) as consumer:
                consumer.qos(prefetch_count=1)
                self._running.set()
                while self.is_running:
                    try:
                        conn.drain_events(timeout=1)
                    except socket.timeout:
                        pass
                    except KeyboardInterrupt:
                        self.stop()
                        LOG.info("Server with id='{0}' stopped.".format(
                            self.server_id))
                        return
        except socket.error as e:
            raise exc.MistralException("Broker connection failed: %s" % e)

    def stop(self):
        """Stop the server."""
        self._running.clear()

    def _get_rpc_method(self, method_name):
        for endpoint in self.endpoints:
            if hasattr(endpoint, method_name):
                return getattr(endpoint, method_name)

        return None

    @staticmethod
    def _set_auth_ctx(ctx):
        if not isinstance(ctx, dict):
            return

        context = auth_ctx.MistralContext(**ctx)
        auth_ctx.set_ctx(context)

        return context

    def publish_message(self, body, reply_to, corr_id, res_type='response'):
        with kombu.producers[self.conn].acquire(block=True) as producer:
            producer.publish(
                body=body,
                exchange=self.exchange,
                routing_key=reply_to,
                correlation_id=corr_id,
                serializer='pickle' if res_type == 'error'
                else 'mistral_serialization',
                type=res_type
            )

    def _on_message_safe(self, request, message):
        try:
            return self._on_message(request, message)
        except Exception as e:
            # Wrap exception into another exception for compability with oslo.
            self.publish_message(
                exc.KombuException(e),
                message.properties['reply_to'],
                message.properties['correlation_id'],
                res_type='error'
            )
        finally:
            message.ack()

    def _on_message(self, request, message):
        LOG.debug('Received message %s',
                  request)

        is_async = request.get('async', False)
        rpc_ctx = request.get('rpc_ctx')
        redelivered = message.delivery_info.get('redelivered', None)
        rpc_method_name = request.get('rpc_method')
        arguments = request.get('arguments')
        correlation_id = message.properties['correlation_id']
        reply_to = message.properties['reply_to']

        if redelivered is not None:
            rpc_ctx['redelivered'] = redelivered

        rpc_context = self._set_auth_ctx(rpc_ctx)

        rpc_method = self._get_rpc_method(rpc_method_name)

        if not rpc_method:
            raise exc.MistralException("No such method: %s" % rpc_method_name)

        response = rpc_method(rpc_ctx=rpc_context, **arguments)

        if not is_async:
            self.publish_message(
                response,
                reply_to,
                correlation_id
            )

    def register_endpoint(self, endpoint):
        self.endpoints.append(endpoint)
