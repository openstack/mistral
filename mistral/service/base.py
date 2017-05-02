# Copyright 2016 - Nokia Networks
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

from eventlet import event
from oslo_service import service

from mistral.service import coordination


class MistralService(service.Service):
    """Base class for Mistral services.

    The term 'service' here means any Mistral component that can run as
    an independent process and thus can be registered as a cluster member.
    """
    def __init__(self, cluster_group, setup_profiler=True):
        super(MistralService, self).__init__()

        self.cluster_member = coordination.Service(cluster_group)
        self._setup_profiler = setup_profiler
        self._started = event.Event()

    def wait_started(self):
        """Wait until the service is fully started."""
        self._started.wait()

    def _notify_started(self, message):
        print(message)

        self._started.send()

    def start(self):
        super(MistralService, self).start()

        self.cluster_member.register_membership()

    def stop(self, graceful=False):
        super(MistralService, self).stop(graceful)

        self._started = event.Event()

        # TODO(rakhmerov): Probably we could also take care of an RPC server
        # if it exists for this particular service type. Take a look at
        # executor and engine servers.

        # TODO(rakhmerov): This method is not implemented correctly now
        # (not thread-safe). Uncomment this call once it's fixed.
        # self.cluster_member.stop()
