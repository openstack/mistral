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

import kombu
from oslo_log import log as logging

from mistral.engine.rpc_backend import base as rpc_base
from mistral.engine.rpc_backend.kombu import base as kombu_base
from mistral import exceptions as exc
from mistral import utils


LOG = logging.getLogger(__name__)
IS_RECEIVED = 'kombu_rpc_is_received'
RESULT = 'kombu_rpc_result'
CORR_ID = 'kombu_rpc_correlation_id'
TYPE = 'kombu_rpc_type'


class KombuRPCClient(rpc_base.RPCClient, kombu_base.Base):
    def __init__(self, conf):
        super(KombuRPCClient, self).__init__(conf)

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
        self._timeout = conf.get('timeout', 60)
        self.conn = self._make_connection(
            self.host,
            self.port,
            self.user_id,
            self.password,
            self.virtual_host
        )

        # Create exchange.
        exchange = self._make_exchange(
            self.exchange,
            durable=self.durable_queue,
            auto_delete=self.auto_delete
        )

        # Create queue.
        queue_name = utils.generate_unicode_uuid()
        self.callback_queue = kombu.Queue(
            queue_name,
            exchange=exchange,
            routing_key=queue_name,
            durable=False,
            exclusive=True,
            auto_delete=True
        )

        # Create consumer.
        self.consumer = kombu.Consumer(
            channel=self.conn.channel(),
            queues=self.callback_queue,
            callbacks=[self._on_response],
            accept=['pickle', 'json']
        )
        self.consumer.qos(prefetch_count=1)

    @staticmethod
    def _on_response(response, message):
        """Callback on response.

        This method is automatically called when a response is incoming and
        decides if it is the message we are waiting for - the message with the
        result.

        :param response: the body of the amqp message already deserialized
            by kombu
        :param message: the plain amqp kombu.message with additional
            information
        """
        LOG.debug("Got response: {0}".format(response))

        try:
            message.ack()
        except Exception as e:
            LOG.exception("Failed to acknowledge AMQP message: %s" % e)
        else:
            LOG.debug("AMQP message acknowledged.")

            # Process response.
            if (utils.get_thread_local(CORR_ID) ==
                    message.properties['correlation_id']):
                utils.set_thread_local(IS_RECEIVED, True)

                if message.properties.get('type') == 'error':
                    utils.set_thread_local(TYPE, 'error')
                utils.set_thread_local(RESULT, response)

    def _wait_for_result(self):
        """Waits for the result from the server.

        Waits for the result from the server, checks every second if
        a timeout occurred. If a timeout occurred - the `RpcTimeout` exception
        will be raised.
        """
        while not utils.get_thread_local(IS_RECEIVED):
            try:
                self.conn.drain_events(timeout=self._timeout)
            except socket.timeout:
                raise exc.MistralException("RPC Request timeout")

    def _call(self, ctx, method, target, async=False, **kwargs):
        """Performs a remote call for the given method.

        :param ctx: authentication context associated with mistral
        :param method: name of the method that should be executed
        :param kwargs: keyword parameters for the remote-method
        :param target: Server name
        :param async: bool value means whether the request is
            asynchronous or not.
        :return: result of the method or None if async.
        """
        utils.set_thread_local(CORR_ID, utils.generate_unicode_uuid())
        utils.set_thread_local(IS_RECEIVED, False)

        self.consumer.consume()

        body = {
            'rpc_ctx': ctx.to_dict(),
            'rpc_method': method,
            'arguments': kwargs,
            'async': async
        }

        LOG.debug("Publish request: {0}".format(body))

        # Publish request.
        with kombu.producers[self.conn].acquire(block=True) as producer:
            producer.publish(
                body=body,
                exchange=self.exchange,
                routing_key=self.topic,
                reply_to=self.callback_queue.name,
                correlation_id=utils.get_thread_local(CORR_ID),
                serializer='mistral_serialization',
                delivery_mode=2
            )

        # Start waiting for response.
        if async:
            return

        self._wait_for_result()
        result = utils.get_thread_local(RESULT)
        res_type = utils.get_thread_local(TYPE)

        self._clear_thread_local()

        if res_type == 'error':
            raise result

        return result

    @staticmethod
    def _clear_thread_local():
        utils.set_thread_local(RESULT, None)
        utils.set_thread_local(CORR_ID, None)
        utils.set_thread_local(IS_RECEIVED, None)
        utils.set_thread_local(TYPE, None)

    def sync_call(self, ctx, method, target=None, **kwargs):
        return self._call(ctx, method, async=False, target=target, **kwargs)

    def async_call(self, ctx, method, target=None, **kwargs):
        return self._call(ctx, method, async=True, target=target, **kwargs)
