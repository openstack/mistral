# Copyright 2017 - Brocade Communications Systems, Inc.
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

from mistral.rpc import clients as rpc_clients


LOG = logging.getLogger(__name__)


class RemoteExecutor(rpc_clients.ExecutorClient):
    """Executor that passes execution request to a remote executor."""

    def __init__(self):
        super(RemoteExecutor, self).__init__(cfg.CONF.executor)
