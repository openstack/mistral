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

import datetime
from tempest.lib import decorators
from tempest.lib import exceptions
from tempest import test

from mistral import utils
from mistral_tempest_tests.tests import base


class ActionTestsV2(base.TestCase):

    _service = 'workflowv2'

    def get_field_value(self, body, act_name, field):
        return [body['actions'][i][field]
                for i in range(len(body['actions']))
                if body['actions'][i]['name'] == act_name][0]

    def tearDown(self):
        for act in self.client.actions:
            self.client.delete_obj('actions', act)
        self.client.actions = []

        super(ActionTestsV2, self).tearDown()

    @test.attr(type='smoke')
    @decorators.idempotent_id('2e1a578a-1c27-409a-96be-84b5c41498cd')
    def test_get_list_actions(self):
        resp, body = self.client.get_list_obj('actions')

        self.assertEqual(200, resp.status)
        self.assertNotEqual([], body['actions'])
        self.assertNotIn('next', body)

    @test.attr(type='smoke')
    @decorators.idempotent_id('786ee85c-c32d-4ac9-8f45-79ab6bc47ef1')
    def test_get_list_actions_with_pagination(self):
        resp, body = self.client.get_list_obj(
            'actions?limit=1&sort_keys=name&sort_dirs=desc'
        )

        self.assertEqual(200, resp.status)
        self.assertEqual(1, len(body['actions']))
        self.assertIn('next', body)

        name_1 = body['actions'][0].get('name')
        next = body.get('next')

        param_dict = utils.get_dict_from_string(
            next.split('?')[1],
            delimiter='&'
        )

        # NOTE: 'id' gets included into sort keys automatically with 'desc'
        # sorting to avoid pagination looping.
        expected_sub_dict = {
            'limit': 1,
            'sort_keys': 'name,id',
            'sort_dirs': 'desc,asc'
        }

        self.assertDictContainsSubset(expected_sub_dict, param_dict)

        # Query again using 'next' hint
        url_param = next.split('/')[-1]
        resp, body = self.client.get_list_obj(url_param)

        self.assertEqual(200, resp.status)
        self.assertEqual(1, len(body['actions']))

        name_2 = body['actions'][0].get('name')

        self.assertGreater(name_1, name_2)

    @test.attr(type='negative')
    @decorators.idempotent_id('5148358e-200f-49c7-8e88-1ddeec61c6a9')
    def test_get_list_actions_nonexist_sort_dirs(self):
        context = self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'actions?limit=1&sort_keys=id&sort_dirs=nonexist'
        )

        self.assertIn(
            'Unknown sort direction',
            context.resp_body.get('faultstring')
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('85482ce8-70f4-47a6-9e80-de1ac22b6412')
    def test_get_list_actions_invalid_limit(self):
        context = self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'actions?limit=-1&sort_keys=id&sort_dirs=asc'
        )

        self.assertIn(
            'Limit must be positive',
            context.resp_body.get('faultstring')
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('a203e75b-2013-422f-b9eb-da4375041058')
    def test_get_list_actions_duplicate_sort_keys(self):
        context = self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'actions?limit=1&sort_keys=id,id&sort_dirs=asc,asc'
        )

        self.assertIn(
            'Length of sort_keys must be equal or greater than sort_dirs',
            context.resp_body.get('faultstring')
        )

    @test.attr(type='smoke')
    @decorators.idempotent_id('9a53af71-8f1e-4ad5-b572-2c4c621715c0')
    def test_get_list_actions_equal_to_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        resp, body = self.client.get_list_obj(
            'actions?is_system=False'
        )

        self.assertEqual(200, resp.status)
        self.assertNotEqual([], body['actions'])

        for act in body['actions']:
            self.assertFalse(act['is_system'])

    @test.attr(type='smoke')
    @decorators.idempotent_id('3c3d28ce-9490-41ae-a918-c28f843841e1')
    def test_get_list_actions_not_equal_to_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        resp, body = self.client.get_list_obj(
            'actions?is_system=neq:False'
        )

        self.assertEqual(200, resp.status)
        self.assertNotEqual([], body['actions'])

        for act in body['actions']:
            self.assertTrue(act['is_system'])

    @test.attr(type='smoke')
    @decorators.idempotent_id('84823a84-5caa-427d-8a2c-622a1d1893b1')
    def test_get_list_actions_in_list_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        created_acts = [action['name'] for action in body['actions']]
        _, body = self.client.get_object('actions', created_acts[0])
        time = body['created_at']
        resp, body = self.client.get_list_obj(
            'actions?created_at=in:' + time.replace(' ', '%20')
        )

        self.assertEqual(200, resp.status)
        action_names = [action['name'] for action in body['actions']]
        self.assertListEqual(created_acts, action_names)

    @test.attr(type='smoke')
    @decorators.idempotent_id('4b05dfcf-ef39-4032-9528-c8422c7329dd')
    def test_get_list_actions_not_in_list_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        created_acts = [action['name'] for action in body['actions']]
        _, body = self.client.get_object('actions', created_acts[0])
        time = body['created_at']
        resp, body = self.client.get_list_obj(
            'actions?created_at=nin:' + time.replace(' ', '%20')
        )

        self.assertEqual(200, resp.status)
        action_names = [action['name'] for action in body['actions']]
        for act in created_acts:
            self.assertNotIn(act, action_names)

    @test.attr(type='smoke')
    @decorators.idempotent_id('20b3d527-447d-492b-8cb7-ac5e3757d7d5')
    def test_get_list_actions_greater_than_filter(self):
        time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        resp, body = self.client.get_list_obj(
            'actions?created_at=gt:' + time.replace(' ', '%20')
        )

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['actions'])

    @test.attr(type='smoke')
    @decorators.idempotent_id('7f598dba-f169-47ec-a487-f0ed31484aff')
    def test_get_list_actions_greater_than_equal_to_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        created_acts = [action['name'] for action in body['actions']]
        _, body = self.client.get_object('actions', created_acts[0])
        time = body['created_at']
        resp, body = self.client.get_list_obj(
            'actions?created_at=gte:' + time.replace(' ', '%20')
        )

        actions = [action['name'] for action in body['actions']]
        self.assertEqual(200, resp.status)
        self.assertIn(created_acts[0], actions)

    @test.attr(type='smoke')
    @decorators.idempotent_id('874fb57d-a762-4dc3-841d-396657510d23')
    def test_get_list_actions_less_than_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        created_acts = [action['name'] for action in body['actions']]
        _, body = self.client.get_object('actions', created_acts[0])
        time = body['created_at']
        resp, body = self.client.get_list_obj(
            'actions?created_at=lt:' + time.replace(' ', '%20')
        )

        actions = [action['name'] for action in body['actions']]
        self.assertEqual(200, resp.status)
        self.assertNotIn(created_acts[0], actions)

    @test.attr(type='smoke')
    @decorators.idempotent_id('1fda6c31-b0c3-4b78-9f67-b920e1f6c973')
    def test_get_list_actions_less_than_equal_to_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        created_acts = [action['name'] for action in body['actions']]
        _, body = self.client.get_object('actions', created_acts[0])
        time = body['created_at']
        resp, body = self.client.get_list_obj(
            'actions?created_at=lte:' + time.replace(' ', '%20')
        )

        actions = [action['name'] for action in body['actions']]
        self.assertEqual(200, resp.status)
        self.assertIn(created_acts[0], actions)

    @test.attr(type='smoke')
    @decorators.idempotent_id('cbb716f1-7fc7-4884-8fa9-6ff2bc35ee29')
    def test_get_list_actions_multiple_filter(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        created_acts = [action['name'] for action in body['actions']]
        _, body = self.client.get_object('actions', created_acts[0])
        time = body['created_at']
        resp, body = self.client.get_list_obj(
            'actions?created_at=lte:' + time.replace(' ', '%20') +
            '&is_system=False'
        )

        actions = [action['name'] for action in body['actions']]
        self.assertEqual(200, resp.status)
        self.assertIn(created_acts[0], actions)

    @test.attr(type='negative')
    @decorators.idempotent_id('45fdc1f3-4d89-4035-9b76-08ef94c92628')
    def test_get_list_actions_invalid_filter(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'actions?is_system<False'
        )
        self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'actions?is_system!=False'
        )
        self.assertRaises(
            exceptions.BadRequest,
            self.client.get_list_obj,
            'actions?created_at>2016-02-23%2008:51:26'
        )

    @test.attr(type='sanity')
    @decorators.idempotent_id('5dbceaf3-6a32-4a4f-9427-1bbdb6f3c574')
    def test_create_and_delete_few_actions(self):
        resp, body = self.client.create_action('action_v2.yaml')
        self.assertEqual(201, resp.status)

        created_acts = [action['name'] for action in body['actions']]

        resp, body = self.client.get_list_obj('actions')
        self.assertEqual(200, resp.status)

        actions = [action['name'] for action in body['actions']]

        for act in created_acts:
            self.assertIn(act, actions)
            self.client.delete_obj('actions', act)

        _, body = self.client.get_list_obj('actions')
        actions = [action['name'] for action in body['actions']]

        for act in created_acts:
            self.assertNotIn(act, actions)
            self.client.actions.remove(act)

    @test.attr(type='sanity')
    @decorators.idempotent_id('d7dad5de-6b1f-4813-b789-78f075252639')
    def test_get_action(self):
        _, body = self.client.create_action('action_v2.yaml')
        action_name = body['actions'][0]['name']
        resp, body = self.client.get_object('actions', action_name)

        self.assertEqual(200, resp.status)
        self.assertEqual(action_name, body['name'])

    @test.attr(type='sanity')
    @decorators.idempotent_id('21a031c8-8e2d-421f-8dfe-71a3b5e44381')
    def test_update_action(self):
        _, body = self.client.create_action('action_v2.yaml')
        action = body['actions'][0]['name']

        act_created_at = self.get_field_value(
            body=body, act_name=action, field='created_at')

        self.assertNotIn('updated at', body['actions'])

        resp, body = self.client.update_request('actions', 'action_v2.yaml')
        self.assertEqual(200, resp.status)

        actions = [act['name'] for act in body['actions']]
        self.assertIn(action, actions)

        updated_act_created_at = self.get_field_value(
            body=body, act_name=action, field='created_at')

        self.assertEqual(act_created_at.split(".")[0], updated_act_created_at)
        self.assertTrue(all(['updated_at' in item
                             for item in body['actions']]))

    @test.attr(type='sanity')
    @decorators.idempotent_id('329b1030-c55c-45f0-8129-cc892bc23dcc')
    def test_get_action_definition(self):
        _, body = self.client.create_action('action_v2.yaml')
        act_name = body['actions'][0]['name']

        resp, body = self.client.get_definition('actions', act_name)
        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)
        self.assertIn(act_name, body)

    @test.attr(type='negative')
    @decorators.idempotent_id('c2b5be88-571a-4855-922f-9a338dba6adb')
    def test_get_nonexistent_action(self):
        self.assertRaises(
            exceptions.NotFound,
            self.client.get_object,
            'actions', 'nonexist'
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('fc2fafcb-9bb4-4a18-a507-3f9964f4a08a')
    def test_double_creation(self):
        self.client.create_action('action_v2.yaml')

        self.assertRaises(
            exceptions.Conflict,
            self.client.create_action,
            'action_v2.yaml'
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('0c456a73-9c39-4aeb-b3ca-3ea4338bc9ab')
    def test_create_action_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_action,
            'wb_v2.yaml'
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('469677b5-22ab-4e2a-aee6-5bcc9dac93de')
    def test_update_action_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.update_request,
            'actions', 'wb_v2.yaml'
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('ab444607-40fc-47cb-982f-83762d5b64c9')
    def test_delete_nonexistent_action(self):
        self.assertRaises(
            exceptions.NotFound,
            self.client.delete_obj,
            'actions', 'nonexist'
        )

    @test.attr(type='negative')
    @decorators.idempotent_id('74d0d480-793a-46ca-b88a-8336c1897f3a')
    def test_delete_standard_action(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.delete_obj,
            'actions', 'nova.servers_create'
        )
