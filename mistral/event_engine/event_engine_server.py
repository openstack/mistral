# Copyright 2016 - Nokia Networks
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

from oslo_log import log as logging

from mistral import config as cfg
from mistral.event_engine import default_event_engine as evt_eng
from mistral.rpc import base as rpc
from mistral.service import base as service_base
from mistral.utils import profiler as profiler_utils


LOG = logging.getLogger(__name__)


class EventEngineServer(service_base.MistralService):
    """RPC EventEngine server.

    This class manages event engine life-cycle and gets registered as
    an RPC endpoint to process event engine specific calls. It also
    registers a cluster member associated with this instance of event
    engine.
    """

    def __init__(self, event_engine):
        super(EventEngineServer, self).__init__('event_engine_group')

        self._event_engine = event_engine
        self._rpc_server = None

    def start(self):
        super(EventEngineServer, self).start()

        profiler_utils.setup(
            'mistral-event-engine',
            cfg.CONF.event_engine.host
        )

        # Initialize and start RPC server.

        self._rpc_server = rpc.get_rpc_server_driver()(cfg.CONF.event_engine)
        self._rpc_server.register_endpoint(self)

        self._rpc_server.run()

        self._notify_started('Event engine server started.')

    def stop(self, graceful=False):
        super(EventEngineServer, self).stop(graceful)

        if self._rpc_server:
            self._rpc_server.stop(graceful)

    def create_event_trigger(self, rpc_ctx, trigger, events):
        LOG.info(
            "Received RPC request 'create_event_trigger'[rpc_ctx=%s,"
            " trigger=%s, events=%s", rpc_ctx, trigger, events
        )

        return self._event_engine.create_event_trigger(trigger, events)

    def delete_event_trigger(self, rpc_ctx, trigger, events):
        LOG.info(
            "Received RPC request 'delete_event_trigger'[rpc_ctx=%s,"
            " trigger=%s, events=%s", rpc_ctx, trigger, events
        )

        return self._event_engine.delete_event_trigger(trigger, events)

    def update_event_trigger(self, rpc_ctx, trigger):
        LOG.info(
            "Received RPC request 'update_event_trigger'[rpc_ctx=%s,"
            " trigger=%s", rpc_ctx, trigger
        )

        return self._event_engine.update_event_trigger(trigger)


def get_oslo_service():
    return EventEngineServer(evt_eng.DefaultEventEngine())
