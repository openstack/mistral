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

import json
import pecan
from pecan import hooks

from mistral.db.v2 import api as db_api
from mistral.services import maintenance as maintenance_service

ALLOWED_WITHOUT_AUTH = ['/', '/v2/', '/health', '/maintenance']


def _complete_async_action(maintenance_mode, state):
    return (state.request.method == 'PUT' and
            '/v2/action_executions' in state.request.path and
            maintenance_mode == maintenance_service.PAUSING
            )


def _put_method_executions(maintenance_mode, state):
    if not (state.request.method == 'PUT' and
            '/v2/executions' in state.request.path):
        return False

    body = json.loads(state.request.body.decode('utf8').replace("'", '"'))
    return ('state' in body and body['state'] == 'CANCELLED' and
            (maintenance_mode == maintenance_service.PAUSING or
             maintenance_mode == maintenance_service.PAUSED
             ))


class MaintenanceHook(hooks.PecanHook):

    def before(self, state):
        if state.request.path in ALLOWED_WITHOUT_AUTH or \
                state.request.method == 'GET':
            return

        cluster_state = db_api.get_maintenance_status()

        if (cluster_state == maintenance_service.RUNNING or
                _complete_async_action(cluster_state, state) or
                _put_method_executions(cluster_state, state)):
            return

        msg = "Current Mistral state is {}. Method is not allowed".format(
            cluster_state
        )

        pecan.abort(
            status_code=423,
            detail=msg,
            headers={'Server-Error-Message': msg}
        )
