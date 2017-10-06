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

import amqp
import socket
import threading
import time

import kombu
from oslo_config import cfg
from oslo_log import log as logging
from stevedore import driver

from mistral import context as auth_ctx
from mistral import exceptions as exc
from mistral.rpc import base as rpc_base
from mistral.rpc.kombu import base as kombu_base
from mistral.rpc.kombu import kombu_hosts


LOG = logging.getLogger(__name__)

CONF = cfg.CONF

_pool_opts = [
    cfg.IntOpt(
        'executor_thread_pool_size',
        default=64,
        deprecated_name="rpc_thread_pool_size",
        help='Size of executor thread pool when'
        ' executor is threading or eventlet.'
    ),
]


class KombuRPCServer(rpc_base.RPCServer, kombu_base.Base):
    def __init__(self, conf):
        super(KombuRPCServer, self).__init__(conf)

        CONF.register_opts(_pool_opts)

        kombu_base.set_transport_options()

        self._register_mistral_serialization()

        self.topic = conf.topic
        self.server_id = conf.host

        self._hosts = kombu_hosts.KombuHosts(CONF)

        self._executor_threads = CONF.executor_thread_pool_size
        self.exchange = CONF.control_exchange
        # TODO(rakhmerov): We shouldn't rely on any properties related
        # to oslo.messaging. Only "transport_url" should matter.
        self.virtual_host = CONF.oslo_messaging_rabbit.rabbit_virtual_host
        self.durable_queue = CONF.oslo_messaging_rabbit.amqp_durable_queues
        self.auto_delete = CONF.oslo_messaging_rabbit.amqp_auto_delete
        self.routing_key = self.topic
        self.channel = None
        self.conn = None
        self._running = threading.Event()
        self._stopped = threading.Event()
        self.endpoints = []
        self._worker = None
        self._thread = None

        # TODO(ddeja): Those 2 options should be gathered from config.
        self._sleep_time = 1
        self._max_sleep_time = 10

    @property
    def is_running(self):
        """Return whether server is running."""
        return self._running.is_set()

    def run(self, executor='blocking'):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, args=(executor,))
            self._thread.daemon = True
            self._thread.start()

    def _run(self, executor):
        """Start the server."""
        self._prepare_worker(executor)

        while True:
            try:
                _retry_connection = False
                host = self._hosts.get_host()

                self.conn = self._make_connection(
                    host.hostname,
                    host.port,
                    host.username,
                    host.password,
                    self.virtual_host,
                )

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
                        callbacks=[self._process_message],
                ) as consumer:
                    consumer.qos(prefetch_count=1)

                    self._running.set()
                    self._stopped.clear()

                    LOG.info(
                        "Connected to AMQP at %s:%s",
                        host.hostname,
                        host.port
                    )
                    self._sleep_time = 1

                    while self.is_running:
                        try:
                            conn.drain_events(timeout=1)
                        except socket.timeout:
                            pass
                        except KeyboardInterrupt:
                            self.stop()

                            LOG.info(
                                "Server with id='%w' stopped.",
                                self.server_id
                            )

                            return
            except (socket.error, amqp.exceptions.ConnectionForced) as e:
                LOG.debug("Broker connection failed: %s", e)

                _retry_connection = True
            finally:
                self._stopped.set()

                if _retry_connection:
                    LOG.debug(
                        "Sleeping for %s seconds, then retrying "
                        "connection",
                        self._sleep_time
                    )

                    time.sleep(self._sleep_time)

                    self._sleep_time = min(
                        self._sleep_time * 2,
                        self._max_sleep_time
                    )

    def stop(self, graceful=False):
        self._running.clear()

        if graceful:
            self.wait()

    def wait(self):
        self._stopped.wait()

        try:
            self._worker.shutdown(wait=True)
        except AttributeError as e:
            LOG.warning("Cannot stop worker in graceful way: %s", e)

    def _get_rpc_method(self, method_name):
        for endpoint in self.endpoints:
            if hasattr(endpoint, method_name):
                return getattr(endpoint, method_name)

        return None

    @staticmethod
    def _set_auth_ctx(ctx):
        if not isinstance(ctx, dict):
            return

        context = auth_ctx.MistralContext.from_dict(ctx)
        auth_ctx.set_ctx(context)

        return context

    def publish_message(self, body, reply_to, corr_id, res_type='response'):
        if res_type != 'error':
            body = self._serialize_message({'body': body})

        with kombu.producers[self.conn].acquire(block=True) as producer:
            producer.publish(
                body=body,
                exchange=self.exchange,
                routing_key=reply_to,
                correlation_id=corr_id,
                serializer='pickle' if res_type == 'error' else 'json',
                type=res_type
            )

    def _on_message_safe(self, request, message):
        try:
            return self._on_message(request, message)
        except Exception as e:
            LOG.warning(
                "Got exception while consuming message. Exception would be "
                "send back to the caller."
            )
            LOG.debug("Exceptions: %s", str(e))

            # Wrap exception into another exception for compatibility
            # with oslo.
            self.publish_message(
                exc.KombuException(e),
                message.properties['reply_to'],
                message.properties['correlation_id'],
                res_type='error'
            )
        finally:
            message.ack()

    def _on_message(self, request, message):
        LOG.debug('Received message %s', request)

        is_async = request.get('async', False)
        rpc_ctx = request.get('rpc_ctx')
        redelivered = message.delivery_info.get('redelivered')
        rpc_method_name = request.get('rpc_method')
        arguments = self._deserialize_message(request.get('arguments'))
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
            LOG.debug(
                "RPC server sent a reply [reply_to = %s, correlation_id = %s",
                reply_to,
                correlation_id
            )

            self.publish_message(
                response,
                reply_to,
                correlation_id
            )

    def register_endpoint(self, endpoint):
        self.endpoints.append(endpoint)

    def _process_message(self, request, message):
        self._worker.submit(self._on_message_safe, request, message)

    def _prepare_worker(self, executor='blocking'):
        mgr = driver.DriverManager('kombu_driver.executors', executor)

        executor_opts = {}

        if executor == 'threading':
            executor_opts['max_workers'] = self._executor_threads

        self._worker = mgr.driver(**executor_opts)
