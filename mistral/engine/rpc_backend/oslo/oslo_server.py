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

from oslo_log import log as logging
import oslo_messaging as messaging

from mistral import context as ctx
from mistral.engine.rpc_backend import base as rpc_base
from mistral.engine.rpc_backend import rpc


LOG = logging.getLogger(__name__)


class OsloRPCServer(rpc_base.RPCServer):
    def __init__(self, conf):
        super(OsloRPCServer, self).__init__(conf)

        self.topic = conf.get('topic', '')
        self.server_id = conf.get('server_id', '')
        self.queue = self.topic
        self.routing_key = self.topic
        self.channel = None
        self.connection = None
        self.endpoints = []

    def register_endpoint(self, endpoint):
        self.endpoints.append(endpoint)

    def run(self, executor='blocking'):
        target = messaging.Target(
            topic=self.topic,
            server=self.server_id
        )

        server = messaging.get_rpc_server(
            rpc.get_transport(),
            target,
            self.endpoints,
            executor=executor,
            serializer=ctx.RpcContextSerializer(ctx.JsonPayloadSerializer())
        )

        server.start()
        server.wait()
