# Copyright 2014 Mirantis, Inc.
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

from tempest import exceptions
from tempest import test

from mistral.tests.functional.api.v1 import test_mistral_basic
from mistral.tests.functional import base


class WorkbookTestsV2(test_mistral_basic.WorkbookTestsV1):

    _version = 2

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkbookTestsV2, self).tearDown()


class WorkflowTestsV2(base.TestCase):

    _version = 2

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkflowTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_workflows(self):
        resp, body = self.client.get_list_obj('workflows')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['workflows'])

    @test.attr(type='smoke')
    def test_create_and_delete_workflow(self):
        resp, body = self.client.create_workflow()

        self.assertEqual(201, resp.status)
        self.assertEqual('wf', body['workflows'][0]['name'])

        resp, body = self.client.get_list_obj('workflows')

        self.assertEqual(200, resp.status)
        names = [wf['name'] for wf in body['workflows']]
        self.assertIn('wf', names)

        self.client.delete_obj('workflows', 'wf')
        self.client.workflows.remove('wf')

        _, body = self.client.get_list_obj('workflows')

        names = [wf['name'] for wf in body['workflows']]
        self.assertNotIn('wf', names)

    @test.attr(type='smoke')
    def test_get_workflow(self):
        self.client.create_workflow()
        resp, body = self.client.get_object('workflows', 'wf')

        self.assertEqual(200, resp.status)
        self.assertEqual('wf', body['name'])

    @test.attr(type='smoke')
    def test_update_workflow(self):
        self.client.create_workflow()
        resp, body = self.client.update_workflow()

        self.assertEqual(200, resp.status)
        self.assertEqual('wf', body['workflows'][0]['name'])

    @test.attr(type='smoke')
    def test_get_workflow_definition(self):
        self.client.create_workflow()
        resp, body = self.client.get_workflow_definition('wf')

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)


class ExecutionTestsV2(test_mistral_basic.ExecutionTestsV1):

    _version = 2

    def setUp(self):
        super(ExecutionTestsV2, self).setUp()

        self.entity_type = 'workflow_name'
        self.entity_name = 'test.test'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(ExecutionTestsV2, self).tearDown()


class CronTriggerTestsV2(base.TestCase):

    _version = 2

    def setUp(self):
        super(CronTriggerTestsV2, self).setUp()

        _, body = self.client.create_workflow()
        self.wf_name = body['workflows'][0]['name']

    def tearDown(self):

        for tr in self.client.triggers:
            self.client.delete_obj('cron_triggers', tr)
        self.client.triggers = []

        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(CronTriggerTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_cron_triggers(self):
        resp, body = self.client.get_list_obj('cron_triggers')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['cron_triggers'])

    @test.attr(type='sanity')
    def test_create_and_delete_cron_triggers(self):
        tr_name = 'trigger'

        resp, body = self.client.create_cron_trigger(
            tr_name, '5 * * * *', self.wf_name)
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name, body['name'])

        resp, body = self.client.get_list_obj('cron_triggers')
        self.assertEqual(200, resp.status)

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertIn(tr_name, trs_names)

        self.client.delete_obj('cron_triggers', tr_name)
        self.client.triggers.remove(tr_name)

        _, body = self.client.get_list_obj('cron_triggers')

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertNotIn(tr_name, trs_names)

    @test.attr(type='sanity')
    def test_create_two_cron_triggers_for_one_wf(self):
        tr_name_1 = 'trigger1'
        tr_name_2 = 'trigger2'

        resp, body = self.client.create_cron_trigger(
            tr_name_1, '5 * * * *', self.wf_name)
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name_1, body['name'])

        resp, body = self.client.create_cron_trigger(
            tr_name_2, '15 * * * *', self.wf_name)
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name_2, body['name'])

        resp, body = self.client.get_list_obj('cron_triggers')
        self.assertEqual(200, resp.status)

        trs_names = [tr['name'] for tr in body['cron_triggers']]
        self.assertIn(tr_name_1, trs_names)
        self.assertIn(tr_name_2, trs_names)

    @test.attr(type='sanity')
    def test_get_cron_trigger(self):
        tr_name = 'trigger'
        self.client.create_cron_trigger(
            tr_name, '5 * * * *', self.wf_name)

        resp, body = self.client.get_object('cron_triggers', tr_name)

        self.assertEqual(200, resp.status)
        self.assertEqual(tr_name, body['name'])

    @test.attr(type='negative')
    def test_create_cron_trigger_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_cron_trigger,
                          'trigger', '5 * * * *', 'nonexist')

    @test.attr(type='negative')
    def test_get_nonexistent_cron_trigger(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_object,
                          'cron_triggers', 'trigger')

    @test.attr(type='negative')
    def test_delete_nonexistent_trigger(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'cron_triggers', 'trigger')

    @test.attr(type='negative')
    def test_create_two_cron_triggers_with_same_name(self):
        tr_name = 'trigger'
        self.client.create_cron_trigger(
            tr_name, '5 * * * *', self.wf_name)
        self.assertRaises(exceptions.Conflict,
                          self.client.create_cron_trigger,
                          tr_name, '5 * * * *', self.wf_name)

    @test.skip_because(bug="1383146")
    @test.attr(type='negative')
    def test_create_two_cron_triggers_with_same_pattern(self):
        self.client.create_trigger(
            'trigger1', '5 * * * *', self.wf_name)
        self.assertRaises(exceptions.Conflict,
                          self.client.create_cron_trigger,
                          'trigger2', '5 * * * *', self.wf_name)

    @test.attr(type='nagative')
    def test_invalid_cron_pattern_not_enough_params(self):
        self.assertRaises(exceptions.ServerFault,
                          self.client.create_cron_trigger,
                          'trigger', '5 *', self.wf_name)

    @test.attr(type='nagative')
    def test_invalid_cron_pattern_out_of_range(self):
        self.assertRaises(exceptions.ServerFault,
                          self.client.create_cron_trigger,
                          'trigger', '88 * * * *', self.wf_name)


class ActionTestsV2(base.TestCase):

    _version = 2

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
    def test_get_list_actions(self):
        resp, body = self.client.get_list_obj('actions')

        self.assertEqual(200, resp.status)
        self.assertNotEqual([], body['actions'])

    @test.attr(type='sanity')
    def test_create_and_delete_few_actions(self):
        text = base.get_resource('resources/action_v2.yaml')
        action1_name = 'greeting'
        action2_name = 'farewell'

        resp, body = self.client.create_action(text)
        self.assertEqual(201, resp.status)

        actions = [action['name'] for action in body['actions']]
        self.assertIn(action1_name, actions)
        self.assertIn(action2_name, actions)

        resp, body = self.client.get_list_obj('actions')
        self.assertEqual(200, resp.status)

        actions = [action['name'] for action in body['actions']]
        self.assertIn(action1_name, actions)
        self.assertIn(action2_name, actions)

        self.client.delete_obj('actions', action1_name)
        self.client.delete_obj('actions', action2_name)

        _, body = self.client.get_list_obj('actions')

        actions = [action['name'] for action in body['actions']]
        self.assertNotIn(action1_name, actions)
        self.assertNotIn(action2_name, actions)
        self.client.actions.remove(action1_name)
        self.client.actions.remove(action2_name)

    @test.attr(type='sanity')
    def test_get_action(self):
        text = base.get_resource('resources/action_v2.yaml')
        action1_name = 'greeting'
        self.client.create_action(text)

        resp, body = self.client.get_object('actions', action1_name)

        self.assertEqual(200, resp.status)
        self.assertEqual(action1_name, body['name'])

    @test.attr(type='sanity')
    def test_update_action(self):
        text = base.get_resource('resources/action_v2.yaml')
        act1_name = 'greeting'
        act2_name = 'farewell'

        resp, body = self.client.create_action(text)
        act1_created_at = self.get_field_value(
            body=body, act_name=act1_name, field='created_at')
        act2_created_at = self.get_field_value(
            body=body, act_name=act2_name, field='created_at')

        self.assertNotIn('updated at', body['actions'])

        resp, body = self.client.update_action(text)
        self.assertEqual(200, resp.status)

        actions = [action['name'] for action in body['actions']]
        self.assertIn(act1_name, actions)
        self.assertIn(act2_name, actions)

        updated1_created_at = self.get_field_value(
            body=body, act_name=act1_name, field='created_at')
        updated2_created_at = self.get_field_value(
            body=body, act_name=act2_name, field='created_at')

        self.assertEqual(act1_created_at.split(".")[0], updated1_created_at)
        self.assertEqual(act2_created_at.split(".")[0], updated2_created_at)
        self.assertTrue(all(['updated_at' in item
                             for item in body['actions']]))

    @test.attr(type='sanity')
    def test_get_action_definition(self):
        text = base.get_resource('resources/action_v2.yaml')
        action1_name = 'greeting'
        action2_name = 'farewell'
        self.client.create_action(text)

        resp, body = self.client.get_action_definition(action1_name)
        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

        resp, body = self.client.get_action_definition(action2_name)
        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='negative')
    def test_get_nonexistent_action(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_object,
                          'actions', 'nonexist')

    @test.attr(type='negative')
    def test_double_creation(self):
        text = base.get_resource('resources/action_v2.yaml')
        self.client.create_action(text)

        self.assertRaises(exceptions.Conflict,
                          self.client.create_action,
                          text)

    @test.attr(type='negative')
    def test_create_action_invalid_def(self):
        self.assertRaises(exceptions.ServerFault,
                          self.client.create_action, "")

    @test.attr(type='negative')
    def test_update_action_invalid_def(self):
        self.assertRaises(exceptions.ServerFault,
                          self.client.update_action, "")

    @test.attr(type='negative')
    def test_delete_nonexistent_action(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'actions', 'nonexist')

    @test.attr(type='negative')
    def test_delete_standard_action(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.delete_obj,
                          'actions', 'nova.servers_create')
