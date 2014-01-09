# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from mistral.engine import states
from mistral.engine.single import actions
from mistral.openstack.common import processutils
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class MistralTask(object):
    def __init__(self, name, dsl, allows=None, depends_on=None):
        self.name = name
        self.allows = allows or []
        self.depends_on = depends_on or []
        self.id = None
        self.state = states.IDLE
        self.dsl = dsl
        self.result = None
        task = self.dsl.get_tasks()[self.name]
        task_params = task['parameters'] or {}
        self.service_dsl = self.dsl.get_service(task['service_name'])
        self.action_dsl = self.dsl.get_action(task['action'])
        service_type = self.dsl.get_service(task['service_name'])['type']
        service_parameters = \
            self.dsl.get_service(task['service_name'])['parameters']
        if service_type not in actions.get_possible_service_types():
            raise processutils.InvalidArgumentError(
                "Error. Impossible service type: " + service_type)
        self.action = actions.get_action(service_type, self.action_dsl,
                                         task_params, service_parameters)

    def run(self, *args, **kwargs):
        LOG.info("Task is started - %s" % self.name)
        return self.action.run(*args, **kwargs)
