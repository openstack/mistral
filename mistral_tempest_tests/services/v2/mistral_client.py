# Copyright 2016 NEC Corporation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json

from oslo_utils import uuidutils
from tempest import config

from mistral_tempest_tests.services import base

CONF = config.CONF


class MistralClientV2(base.MistralClientBase):

    def post_request(self, url, file_name):
        headers = {"headers": "Content-Type:text/plain"}

        return self.post(url, base.get_resource(file_name), headers=headers)

    def post_json(self, url, obj, extra_headers={}):
        headers = {"Content-Type": "application/json"}
        headers = dict(headers, **extra_headers)
        return self.post(url, json.dumps(obj), headers=headers)

    def update_request(self, url, file_name):
        headers = {"headers": "Content-Type:text/plain"}

        resp, body = self.put(
            url,
            base.get_resource(file_name),
            headers=headers
        )

        return resp, json.loads(body)

    def get_definition(self, item, name):
        resp, body = self.get("%s/%s" % (item, name))

        return resp, json.loads(body)['definition']

    def create_workbook(self, yaml_file):
        resp, body = self.post_request('workbooks', yaml_file)

        wb_name = json.loads(body)['name']
        self.workbooks.append(wb_name)

        _, wfs = self.get_list_obj('workflows')

        for wf in wfs['workflows']:
            if wf['name'].startswith(wb_name):
                self.workflows.append(wf['name'])

        return resp, json.loads(body)

    def create_workflow(self, yaml_file, scope=None):
        if scope:
            resp, body = self.post_request('workflows?scope=public', yaml_file)
        else:
            resp, body = self.post_request('workflows', yaml_file)

        for wf in json.loads(body)['workflows']:
            self.workflows.append(wf['name'])

        return resp, json.loads(body)

    def create_execution(self, identifier, wf_input=None, params=None):
        if uuidutils.is_uuid_like(identifier):
            body = {"workflow_id": "%s" % identifier}
        else:
            body = {"workflow_name": "%s" % identifier}

        if wf_input:
            body.update({'input': json.dumps(wf_input)})
        if params:
            body.update({'params': json.dumps(params)})

        resp, body = self.post('executions', json.dumps(body))

        self.executions.append(json.loads(body)['id'])

        return resp, json.loads(body)

    def update_execution(self, execution_id, put_body):
        resp, body = self.put('executions/%s' % execution_id, put_body)

        return resp, json.loads(body)

    def create_cron_trigger(self, name, wf_name, wf_input=None, pattern=None,
                            first_time=None, count=None):
        post_body = {
            'name': name,
            'workflow_name': wf_name,
            'pattern': pattern,
            'remaining_executions': count,
            'first_execution_time': first_time
        }

        if wf_input:
            post_body.update({'workflow_input': json.dumps(wf_input)})

        rest, body = self.post('cron_triggers', json.dumps(post_body))

        self.triggers.append(name)

        return rest, json.loads(body)

    def create_action(self, yaml_file):
        resp, body = self.post_request('actions', yaml_file)

        self.actions.extend(
            [action['name'] for action in json.loads(body)['actions']])

        return resp, json.loads(body)

    def get_wf_tasks(self, wf_name):
        all_tasks = self.get_list_obj('tasks')[1]['tasks']

        return [t for t in all_tasks if t['workflow_name'] == wf_name]

    def create_action_execution(self, request_body, extra_headers={}):
        resp, body = self.post_json('action_executions',
                                    request_body,
                                    extra_headers)

        params = json.loads(request_body.get('params', '{}'))
        if params.get('save_result', False):
            self.action_executions.append(json.loads(body)['id'])

        return resp, json.loads(body)

    def create_event_trigger(self, wf_id, exchange, topic, event, name='',
                             wf_input=None, wf_params=None):
        post_body = {
            'workflow_id': wf_id,
            'exchange': exchange,
            'topic': topic,
            'event': event,
            'name': name
        }

        if wf_input:
            post_body.update({'workflow_input': json.dumps(wf_input)})

        if wf_params:
            post_body.update({'workflow_params': json.dumps(wf_params)})

        rest, body = self.post('event_triggers', json.dumps(post_body))

        event_trigger = json.loads(body)
        self.event_triggers.append(event_trigger['id'])

        return rest, event_trigger
