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

from oslo_log import log as logging
import pecan
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import root as v2_root

LOG = logging.getLogger(__name__)

API_STATUS = wtypes.Enum(str, 'SUPPORTED', 'CURRENT', 'DEPRECATED')


class APIVersion(resource.Resource):
    """API Version."""

    id = wtypes.text
    "The version identifier."

    status = API_STATUS
    "The status of the API (SUPPORTED, CURRENT or DEPRECATED)."

    link = resource.Link
    "The link to the versioned API."

    @classmethod
    def sample(cls):
        return cls(
            id='v1.0',
            status='CURRENT',
            link=resource.Link(
                target_name='v1',
                href='http://example.com:9777/v1'
            )
        )


class RootController(object):
    v2 = v2_root.Controller()

    @wsme_pecan.wsexpose([APIVersion])
    def index(self):
        LOG.debug("Fetching API versions.")

        host_url_v2 = '%s/%s' % (pecan.request.host_url, 'v2')
        api_v2 = APIVersion(
            id='v2.0',
            status='CURRENT',
            link=resource.Link(href=host_url_v2, target='v2')
        )

        return [api_v2]
