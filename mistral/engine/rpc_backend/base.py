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

import abc


class RPCClient(object):
    def __init__(self, conf):
        """Base class for RPCClient's drivers

        RPC Client is responsible for sending requests to RPC Server.
        All RPC client drivers have to inherit from this class.

        :param conf: dict containing credentials such as
            'user_id', 'password', and also exchange and connection info:
            'exchange', 'topic', 'host', 'port', 'virtual_host'.
        """
        self.conf = conf

    @abc.abstractmethod
    def sync_call(self, ctx, method, target=None, **kwargs):
        """Synchronous call of RPC method.

        Blocks the thread and wait for method result.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def async_call(self, ctx, method, target=None, **kwargs):
        """Asynchronous call of RPC method.

        Does not block the thread, just send invoking data to
        the RPC server and immediately returns nothing.
        """
        raise NotImplementedError


class RPCServer(object):
    def __init__(self, conf):
        """Base class for RPCServer's drivers

        RPC Server should listen for request coming from RPC Clients and
        respond to them respectively to the registered endpoints.
        All RPC server drivers have to inherit from this class.

        :param conf: dict containing credentials such as
            'user_id', 'password', and also exchange and connection info:
            'exchange', 'topic', 'rabbit_host', 'rabbit_port', 'virtual_host'.
        """
        self.conf = conf

    @abc.abstractmethod
    def register_endpoint(self, endpoint):
        """Registers a new RPC endpoint.

        :param endpoint: an object containing methods which
         will be used as RPC methods.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self, executor='blocking'):
        """Runs the RPC server.

        """
        raise NotImplementedError
