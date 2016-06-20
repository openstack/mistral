# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import action
from mistral.api.controllers.v2 import action_execution
from mistral.api.controllers.v2 import cron_trigger
from mistral.api.controllers.v2 import environment
from mistral.api.controllers.v2 import event_trigger
from mistral.api.controllers.v2 import execution
from mistral.api.controllers.v2 import service
from mistral.api.controllers.v2 import task
from mistral.api.controllers.v2 import workbook
from mistral.api.controllers.v2 import workflow


class RootResource(resource.Resource):
    """Root resource for API version 2.

    It references all other resources belonging to the API.
    """

    uri = wtypes.text

    # TODO(everyone): what else do we need here?
    # TODO(everyone): we need to collect all the links from API v2.0
    #                 and provide them.


class Controller(object):
    """API root controller for version 2."""

    workbooks = workbook.WorkbooksController()
    actions = action.ActionsController()
    workflows = workflow.WorkflowsController()
    executions = execution.ExecutionsController()
    tasks = task.TasksController()
    cron_triggers = cron_trigger.CronTriggersController()
    environments = environment.EnvironmentController()
    action_executions = action_execution.ActionExecutionsController()
    services = service.ServicesController()
    event_triggers = event_trigger.EventTriggersController()

    @wsme_pecan.wsexpose(RootResource)
    def index(self):
        return RootResource(uri='%s/%s' % (pecan.request.host_url, 'v2'))
