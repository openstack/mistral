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

import pecan
from pecan import rest
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral import context
from mistral.db.v2 import api as db_api
from mistral.services import maintenance
from mistral.utils import rest_utils


class Maintenance(resource.Resource):
    """Maintenance resource."""

    status = str

    @classmethod
    def sample(cls):
        return cls(
            status="1234"
        )


class MaintenanceController(rest.RestController):

    @pecan.expose('json')
    def get(self):
        context.set_ctx(None)

        maintenance_status = db_api.get_maintenance_status()

        return {
            'status': maintenance_status
        }

    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(
        Maintenance,
        body=Maintenance,
        status_code=200
    )
    def put(self, new_maintenance_status):
        context.set_ctx(None)

        maintenance.change_maintenance_mode(new_maintenance_status.status)

        return new_maintenance_status
