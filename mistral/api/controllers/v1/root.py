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

import pecan
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers.v1 import workbook
from mistral.api.controllers import resource


class RootResource(resource.Resource):
    """Root resource for API version 1.

    It references all other resources belonging to the API.
    """

    uri = wtypes.text

    # TODO: what else do we need here?
    # TODO: we need to collect all the links from API v1.0 and provide them


class Controller(object):
    """API root controller for version 1."""

    workbooks = workbook.WorkbooksController()

    @wsme_pecan.wsexpose(RootResource)
    def index(self):
        return RootResource(uri='%s/%s' % (pecan.request.host_url, 'v1'))
