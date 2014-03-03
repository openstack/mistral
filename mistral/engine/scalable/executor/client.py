# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

from oslo import messaging
from oslo.config import cfg

from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class ExecutorClient(object):
    """
    RPC client for the Executor.
    """

    def __init__(self, transport):
        """Construct an RPC client for the Executor.

        :param transport: a messaging transport handle
        :type transport: Transport
        """
        target = messaging.Target(topic=cfg.CONF.executor.topic)
        self._client = messaging.RPCClient(transport, target)

    def handle_task(self, cntx, **kwargs):
        """Send the task request to the Executor for execution.

        :param cntx: a request context dict
        :type cntx: dict
        :param kwargs: a dict of method arguments
        :type kwargs: dict
        """
        return self._client.cast(cntx, 'handle_task', **kwargs)
