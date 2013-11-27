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

import pecan
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import common_types
from mistral.api.controllers.v1 import root as v1_root


API_STATUS = wtypes.Enum(str, 'SUPPORTED', 'CURRENT', 'DEPRECATED')


class APIVersion(wtypes.Base):
    """API Version."""

    id = wtypes.text
    status = API_STATUS
    link = common_types.Link


class RootController(object):

    v1 = v1_root.Controller()

    @wsme_pecan.wsexpose([APIVersion])
    def index(self):
        host_url = '%s/%s' % (pecan.request.host_url, 'v1')
        api_v1 = APIVersion(id='v1.0',
                            status='CURRENT',
                            link=common_types.Link(href=host_url, target='v1'))

        return [api_v1]
