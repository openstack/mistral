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

from mistral import context as auth_ctx
from mistral.engine.rpc_backend import base as rpc_base
from mistral.engine.rpc_backend import rpc


class OsloRPCClient(rpc_base.RPCClient):
    def __init__(self, conf):
        super(OsloRPCClient, self).__init__(conf)
        self.topic = conf.get('topic', '')

        serializer = auth_ctx.RpcContextSerializer(
            auth_ctx.JsonPayloadSerializer())

        self._client = messaging.RPCClient(
            rpc.get_transport(),
            messaging.Target(topic=self.topic),
            serializer=serializer
        )

    def sync_call(self, ctx, method, target=None, **kwargs):
        return self._client.prepare(topic=self.topic, server=target).call(
            ctx,
            method,
            **kwargs
        )

    def async_call(self, ctx, method, target=None, **kwargs):
        return self._client.prepare(topic=self.topic, server=target).cast(
            ctx,
            method,
            **kwargs
        )
