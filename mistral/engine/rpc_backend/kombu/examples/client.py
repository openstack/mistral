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

from mistral.engine.rpc_backend.kombu import kombu_client


# Example of using Kombu based RPC client.
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
    kombu_rpc = kombu_client.KombuRPCClient(conf)

    print(" [x] Requesting ...")

    ctx = type('context', (object,), {'to_dict': lambda self: {}})()

    response = kombu_rpc.sync_call(ctx, 'fib', n=44)

    print(" [.] Got %r" % (response,))


if __name__ == '__main__':
    main()
