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

import yaml
from yaml import error


class Parser(object):
    """Mistral DSL parser.

    Loads a workbook definition in YAML format as described in Mistral DSL
    specification and provides various methods to access DSL entities like
    tasks and actions in a form of dictionary.
    """
    def __init__(self, workbook_definition):
        try:
            self.doc = yaml.safe_load(workbook_definition)
        except error.YAMLError as exc:
            raise RuntimeError("Definition could not be parsed: %s\n"
                               % exc.message)

    def get_services(self):
        services = []
        for service_name in self.doc["Services"]:
            services.append(self.doc["Services"][service_name])
        return services

    def get_service(self, service_name):
        return self.doc["Services"][service_name]

    def get_events(self):
        events_from_doc = self.doc["Workflow"].get("events", None)
        if not events_from_doc:
            return None
        events = []
        for name in events_from_doc:
            event_dict = {'name': name}
            event_dict.update(events_from_doc[name])
            events.append(event_dict)
        return events

    def get_tasks(self):
        tasks = self.doc["Workflow"]["tasks"]

        for task_name, task_dsl in tasks.iteritems():
            task_dsl["service_name"] = task_dsl["action"].split(':')[0]

        return tasks

    def get_action(self, task_action_name):
        service_name = task_action_name.split(':')[0]
        action_name = task_action_name.split(':')[1]
        action = self.get_service(service_name)['actions'][action_name]
        return action

    def get_actions(self, service_name):
        return self.get_service(service_name)['actions']

    def get_service_names(self):
        names = []
        for name in self.doc['Services']:
            names.append(name)
        return names

    def get_event_task_name(self, event_name):
        return self.doc["Workflow"]["events"][event_name]['tasks']
