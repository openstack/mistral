# Copyright 2015 Huawei Technologies Co., Ltd.
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
from pecan import rest
import tooz.coordination
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import resources
from mistral import context
from mistral import exceptions as exc
from mistral.service import coordination
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)


class ServicesController(rest.RestController):
    @rest_utils.wrap_wsme_controller_exception
    @wsme_pecan.wsexpose(resources.Services)
    def get_all(self):
        """Return all services."""
        acl.enforce('services:list', context.ctx())

        LOG.debug("Fetch services.")

        if not cfg.CONF.coordination.backend_url:
            raise exc.CoordinationNotSupportedException("Service API "
                                                        "is not supported.")

        service_coordinator = coordination.get_service_coordinator()

        if not service_coordinator.is_active():
            raise exc.CoordinationException(
                "Failed to connect to coordination backend."
            )

        # Should be the same as LAUNCH_OPTIONS in launch.py
        # At the moment there is a duplication, need to solve it.
        # We cannot depend on launch.py since it uses eventlet monkey patch
        # under wsgi it causes problems
        mistral_services = {'api', 'engine', 'executor',
                            'event-engine', 'notifier'}
        services_list = []
        service_group = ['%s_group' % i for i in mistral_services]

        try:
            for group in service_group:
                members = service_coordinator.get_members(group)

                members_list = [
                    resources.Service.from_dict(
                        {
                            'type': group,
                            'name': member
                        }
                    )
                    for member in members
                ]

                services_list.extend(members_list)
        except tooz.coordination.ToozError as e:
            # In the scenario of network interruption or manually shutdown
            # connection shutdown, ToozError will be raised.
            raise exc.CoordinationException(
                "Failed to get service members from coordination backend. %s"
                % str(e)
            )

        return resources.Services(services=services_list)
