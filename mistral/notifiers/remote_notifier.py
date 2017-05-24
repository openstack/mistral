# Copyright 2018 - Extreme Networks, Inc.
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

from oslo_config import cfg
from oslo_log import log as logging

from mistral.rpc import base as rpc_base
from mistral.rpc import clients as rpc_clients


LOG = logging.getLogger(__name__)


class RemoteNotifier(rpc_clients.NotifierClient):
    """Notifier that passes notification request to a remote notifier."""

    def __init__(self):
        self.topic = cfg.CONF.notifier.topic
        self._client = rpc_base.get_rpc_client_driver()(cfg.CONF.notifier)
