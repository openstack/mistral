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

from mistral.engine.rpc_backend.kombu import kombu_server


# Simple example of endpoint of RPC server, which just
# calculates given fibonacci number.
class MyServer(object):
    cache = {0: 0, 1: 1}

    def fib(self, rpc_ctx, n):
        if self.cache.get(n) is None:
            self.cache[n] = (self.fib(rpc_ctx, n - 1)
                             + self.fib(rpc_ctx, n - 2))
        return self.cache[n]

    def get_name(self, rpc_ctx):
        return self.__class__.__name__


# Example of using Kombu based RPC server.
def main():
    conf = {
        'user_id': 'guest',
        'password': 'secret',
        'exchange': 'my_exchange',
        'topic': 'my_topic',
        'server_id': 'host',
        'host': 'localhost',
        'port': 5672,
        'virtual_host': '/'
    }
    rpc_server = kombu_server.KombuRPCServer(conf)
    rpc_server.register_endpoint(MyServer())
    rpc_server.run()


if __name__ == '__main__':
    main()
