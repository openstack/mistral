# -*- coding: utf-8 -*-
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

from oslo.config import cfg
from oslo import messaging
import six
from stevedore import driver

from mistral import context as auth_context
from mistral import engine
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def get_executor(name, transport):
    mgr = driver.DriverManager(
        namespace='mistral.executor.drivers',
        name=name,
        invoke_on_load=True,
        invoke_kwds={'transport': transport})
    return mgr.driver


@six.add_metaclass(abc.ABCMeta)
class Executor(object):
    """Abstract class for task execution."""

    def __init__(self, transport=None):
        self.transport = engine.get_transport(transport)
        self.engine = engine.EngineClient(self.transport)

    @abc.abstractmethod
    def handle_task(self, cntx, **kwargs):
        raise NotImplementedError()


class ExecutorClient(object):
    """RPC client for the Executor."""

    def __init__(self, transport):
        """Construct an RPC client for the Executor.

        :param transport: a messaging transport handle
        :type transport: Transport
        """
        serializer = auth_context.RpcContextSerializer(
            auth_context.JsonPayloadSerializer())
        target = messaging.Target(topic=cfg.CONF.executor.topic)
        self._client = messaging.RPCClient(transport, target,
                                           serializer=serializer)

    def handle_task(self, cntx, **kwargs):
        """Send the task request to the Executor for execution.

        :param cntx: a request context dict
        :type cntx: MistralContext
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        """
        return self._client.cast(cntx, 'handle_task', **kwargs)
