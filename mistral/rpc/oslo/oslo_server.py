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

import oslo_messaging as messaging
from oslo_messaging.rpc import dispatcher

from mistral import context as ctx
from mistral.rpc import base as rpc


class OsloRPCServer(rpc.RPCServer):
    def __init__(self, conf):
        super(OsloRPCServer, self).__init__(conf)

        self.topic = conf.topic
        self.server_id = conf.host
        self.queue = self.topic
        self.routing_key = self.topic
        self.channel = None
        self.connection = None
        self.endpoints = []
        self.oslo_server = None

    def register_endpoint(self, endpoint):
        self.endpoints.append(endpoint)

    def run(self, executor='eventlet'):
        target = messaging.Target(
            topic=self.topic,
            server=self.server_id
        )

        # TODO(rakhmerov): rpc.get_transport() should be in oslo.messaging
        # related module.
        access_policy = dispatcher.DefaultRPCAccessPolicy
        self.oslo_server = messaging.get_rpc_server(
            rpc.get_transport(),
            target,
            self.endpoints,
            executor=executor,
            serializer=ctx.RpcContextSerializer(),
            access_policy=access_policy
        )

        self.oslo_server.start()

    def stop(self, graceful=False):
        self.oslo_server.stop()

        if graceful:
            self.oslo_server.wait()

    def wait(self):
        self.oslo_server.wait()
