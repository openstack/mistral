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

from pecan import rest
from pecan import expose
from pecan import request

from mistral.openstack.common import log as logging
from mistral.db import api as db_api
from mistral.services import scheduler


LOG = logging.getLogger(__name__)


class WorkbookDefinitionController(rest.RestController):
    @expose()
    def get(self, workbook_name):
        LOG.debug("Fetch workbook definition [workbook_name=%s]" %
                  workbook_name)

        return db_api.workbook_definition_get(workbook_name)

    @expose(content_type="text/plain")
    def put(self, workbook_name):
        text = request.text

        LOG.debug("Update workbook definition [workbook_name=%s, text=%s]" %
                  (workbook_name, text))

        wb = db_api.workbook_definition_put(workbook_name, text)
        scheduler.create_associated_triggers(wb)

        return wb['definition']
