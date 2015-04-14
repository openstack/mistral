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

from tempest import test
from tempest_lib import decorators
from tempest_lib import exceptions

from mistral.tests.functional import base


class WorkbookTestsV2(base.TestCase):

    _service = 'workflowv2'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkbookTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_workbooks(self):
        resp, body = self.client.get_list_obj('workbooks')

        self.assertEqual(200, resp.status)
        self.assertEqual([], body['workbooks'])

    @test.attr(type='sanity')
    def test_create_and_delete_workbook(self):
        resp, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        self.assertEqual(201, resp.status)

        resp, body = self.client.get_list_obj('workbooks')
        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['workbooks'][0]['name'])

        self.client.delete_obj('workbooks', name)
        self.client.workbooks.remove(name)

        _, body = self.client.get_list_obj('workbooks')
        self.assertEqual([], body['workbooks'])

    @test.attr(type='sanity')
    def test_get_workbook(self):
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']

        resp, body = self.client.get_object('workbooks', name)
        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @test.attr(type='sanity')
    def test_update_workbook(self):
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        resp, body = self.client.update_request('workbooks', 'wb_v2.yaml')

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @test.attr(type='sanity')
    def test_get_workbook_definition(self):
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        resp, body = self.client.get_definition('workbooks', name)

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='negative')
    def test_get_nonexistent_workbook_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_definition,
                          'workbooks', 'nonexist')

    @test.attr(type='negative')
    def test_get_nonexistent_workbook(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'workbooks', 'nonexist')

    @test.attr(type='negative')
    def test_double_create_workbook(self):
        _, body = self.client.create_workbook('wb_v2.yaml')
        name = body['name']
        self.assertRaises(exceptions.Conflict,
                          self.client.create_workbook,
                          'wb_v2.yaml')

        self.client.delete_obj('workbooks', name)
        self.client.workbooks.remove(name)
        _, body = self.client.get_list_obj('workbooks')

        self.assertEqual([], body['workbooks'])

    @test.attr(type='negative')
    def test_create_wb_with_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.create_workbook,
            'wb_v1.yaml'
        )

    @test.attr(type='negative')
    def test_update_wb_with_invalid_def(self):
        self.assertRaises(
            exceptions.BadRequest,
            self.client.update_request,
            'workbooks',
            'wb_v1.yaml'
        )


class WorkflowTestsV2(base.TestCase):

    _service = 'workflowv2'

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(WorkflowTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_workflows(self):
        resp, body = self.client.get_list_obj('workflows')
        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]

        self.assertIn('std.create_instance', names)

    @test.attr(type='sanity')
    def test_create_and_delete_workflow(self):
        resp, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        self.assertEqual(201, resp.status)

        resp, body = self.client.get_list_obj('workflows')
        self.assertEqual(200, resp.status)

        names = [wf['name'] for wf in body['workflows']]
        self.assertIn(name, names)

        self.client.delete_obj('workflows', name)
        self.client.workflows.remove(name)

        _, body = self.client.get_list_obj('workflows')

        names = [wf['name'] for wf in body['workflows']]
        self.assertNotIn(name, names)

    @test.attr(type='sanity')
    def test_get_workflow(self):
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.get_object('workflows', name)

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['name'])

    @test.attr(type='sanity')
    def test_update_workflow(self):
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.update_request('workflows', 'wf_v2.yaml')

        self.assertEqual(200, resp.status)
        self.assertEqual(name, body['workflows'][0]['name'])

    @test.attr(type='sanity')
    def test_get_workflow_definition(self):
        _, body = self.client.create_workflow('wf_v2.yaml')
        name = body['workflows'][0]['name']

        resp, body = self.client.get_definition('workflows', name)

        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)

    @test.attr(type='sanity')
    def test_get_workflow_uploaded_in_wb(self):
        _, body = self.client.create_workbook('wb_v2.yaml')
        wb_name = body['name']

        _, body = self.client.get_list_obj('workflows')
        wf_names = [wf['name'] for wf in body['workflows']
                    if wf['name'].startswith(wb_name)]

        self.assertNotEmpty(wf_names)

    @test.attr(type='negative')
    def test_get_nonexistent_workflow_definition(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_definition,
                          'workflows', 'nonexist')

    @test.attr(type='negative')
    def test_get_nonexistent_workflow(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'workflows', 'nonexist')

    @test.attr(type='negative')
    def test_double_create_workflows(self):
        _, body = self.client.create_workflow('wf_v2.yaml')
        self.assertRaises(exceptions.Conflict,
                          self.client.create_workflow,
                          'wf_v2.yaml')

    @test.attr(type='negative')
    def test_create_wf_with_invalid_def(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_workflow,
                          'wb_v1.yaml')

    @test.attr(type='negative')
    def test_update_wf_with_invalid_def(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.update_request,
                          'workflows', 'wb_v1.yaml')

    @test.attr(type='negative')
    def test_delete_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'workflows', 'nonexist')


class ExecutionTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(ExecutionTestsV2, self).setUp()

        _, body = self.client.create_workflow('wf_v2.yaml')
        self.direct_wf = body['workflows'][0]['name']
        self.reverse_wf = body['workflows'][1]

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(ExecutionTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_list_executions(self):
        resp, _ = self.client.get_list_obj('executions')
        self.assertEqual(200, resp.status)

    @test.attr(type='sanity')
    def test_create_execution_for_direct_wf(self):
        resp, body = self.client.create_execution(self.direct_wf)
        exec_id = body['id']
        self.assertEqual(201, resp.status)
        self.assertEqual(self.direct_wf, body['workflow_name'])
        self.assertEqual('RUNNING', body['state'])

        resp, body = self.client.get_list_obj('executions')
        self.assertIn(exec_id,
                      [ex_id['id'] for ex_id in body['executions']])

    @test.attr(type='sanity')
    def test_create_execution_for_reverse_wf(self):
        resp, body = self.client.create_execution(
            self.reverse_wf['name'],
            {self.reverse_wf['input']: "Bye"},
            {"task_name": "goodbye"})

        exec_id = body['id']
        self.assertEqual(201, resp.status)
        self.assertEqual(self.reverse_wf['name'], body['workflow_name'])
        self.assertEqual('RUNNING', body['state'])

        resp, body = self.client.get_list_obj('executions')
        self.assertIn(exec_id,
                      [ex_id['id'] for ex_id in body['executions']])

        resp, body = self.client.get_object('executions', exec_id)
        # TODO(nmakhotkin): Fix this loop. It is infinite now.
        while body['state'] != 'SUCCESS':
            resp, body = self.client.get_object('executions', exec_id)
            self.assertEqual(200, resp.status)
        self.assertEqual('SUCCESS', body['state'])

    @test.attr(type='sanity')
    def test_get_execution(self):
        _, execution = self.client.create_execution(self.direct_wf)

        resp, body = self.client.get_object('executions', execution['id'])

        del execution['state']
        del body['state']

        self.assertEqual(200, resp.status)
        self.assertEqual(execution['id'], body['id'])

    @test.attr(type='sanity')
    def test_update_execution_pause(self):
        _, execution = self.client.create_execution(self.direct_wf)
        resp, body = self.client.update_execution(
            execution['id'], '{"state": "PAUSED"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('PAUSED', body['state'])

    @test.attr(type='sanity')
    def test_update_execution_fail(self):
        _, execution = self.client.create_execution(self.direct_wf)
        resp, body = self.client.update_execution(
            execution['id'], '{"state": "ERROR", "state_info": "Forced"}')

        self.assertEqual(200, resp.status)
        self.assertEqual('ERROR', body['state'])
        self.assertEqual('Forced', body['state_info'])

    @test.attr(type='negative')
    def test_get_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound, self.client.get_object,
                          'executions', '1a2b3c')

    @test.attr(type='negative')
    def test_update_nonexistent_execution(self):
        put_body = '{"state": "STOPPED"}'

        self.assertRaises(exceptions.NotFound,
                          self.client.update_execution,
                          '1a2b3c', put_body)

    @test.attr(type='negative')
    def test_delete_nonexistent_execution(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.delete_obj,
                          'executions', 'nonexist')

    @test.attr(type='negative')
    def test_create_ex_for_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_execution,
                          'nonexist')

    @test.attr(type='negative')
    def test_create_execution_for_reverse_wf_invalid_start_task(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_execution,
                          self.reverse_wf['name'],
                          {self.reverse_wf['input']: "Bye"},
                          {"task_name": "nonexist"})

    @test.attr(type='negative')
    def test_create_execution_forgot_input_params(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_execution,
                          self.reverse_wf['name'],
                          params={"task_name": "nonexist"})


class CronTriggerTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(CronTriggerTestsV2, self).setUp()

        _, body = self.client.create_workflow('wf_v2.yaml')
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
            tr_name, self.wf_name, None, '5 * * * *')
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
    def test_create_and_delete_oneshot_cron_triggers(self):
        tr_name = 'trigger'

        resp, body = self.client.create_cron_trigger(
            tr_name, self.wf_name, None, None, "4242-12-25 13:37")
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name, body['name'])
        self.assertEqual("4242-12-25 13:37:00", body['next_execution_time'])

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
            tr_name_1, self.wf_name, None, '5 * * * *')
        self.assertEqual(201, resp.status)
        self.assertEqual(tr_name_1, body['name'])

        resp, body = self.client.create_cron_trigger(
            tr_name_2, self.wf_name, None, '15 * * * *')
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
            tr_name, self.wf_name, None, '5 * * * *')

        resp, body = self.client.get_object('cron_triggers', tr_name)

        self.assertEqual(200, resp.status)
        self.assertEqual(tr_name, body['name'])

    @test.attr(type='negative')
    def test_create_cron_trigger_nonexistent_wf(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *')

    @test.attr(type='negative')
    def test_create_cron_trigger_invalid_count(self):
        self.assertRaises(exceptions.ServerFault,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', None, "q")

    @test.attr(type='negative')
    def test_create_cron_trigger_negative_count(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', None, -1)

    @test.attr(type='negative')
    def test_create_cron_trigger_invalid_first_date(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, '5 * * * *', "q")

    @test.attr(type='negative')
    def test_create_cron_trigger_count_only(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, None, None, "42")

    @test.attr(type='negative')
    def test_create_cron_trigger_date_and_count_without_pattern(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', 'nonexist', None, None,
                          "4242-12-25 13:37", "42")

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
            tr_name, self.wf_name, None, '5 * * * *')
        self.assertRaises(exceptions.Conflict,
                          self.client.create_cron_trigger,
                          tr_name, self.wf_name, None, '5 * * * *')

    @decorators.skip_because(bug="1383146")
    @test.attr(type='negative')
    def test_create_two_cron_triggers_with_same_pattern(self):
        self.client.create_trigger(
            'trigger1', self.wf_name, None, '5 * * * *')
        self.assertRaises(exceptions.Conflict,
                          self.client.create_cron_trigger,
                          'trigger2', self.wf_name, None, '5 * * * *')

    @test.attr(type='negative')
    def test_invalid_cron_pattern_not_enough_params(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', self.wf_name, None, '5 *')

    @test.attr(type='negative')
    def test_invalid_cron_pattern_out_of_range(self):
        self.assertRaises(exceptions.BadRequest,
                          self.client.create_cron_trigger,
                          'trigger', self.wf_name, None, '88 * * * *')


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
    def test_get_list_actions(self):
        resp, body = self.client.get_list_obj('actions')

        self.assertEqual(200, resp.status)
        self.assertNotEqual([], body['actions'])

    @test.attr(type='sanity')
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
    def test_get_action(self):
        _, body = self.client.create_action('action_v2.yaml')
        action_name = body['actions'][0]['name']
        resp, body = self.client.get_object('actions', action_name)

        self.assertEqual(200, resp.status)
        self.assertEqual(action_name, body['name'])

    @test.attr(type='sanity')
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
    def test_get_action_definition(self):
        _, body = self.client.create_action('action_v2.yaml')
        act_name = body['actions'][0]['name']

        resp, body = self.client.get_definition('actions', act_name)
        self.assertEqual(200, resp.status)
        self.assertIsNotNone(body)
        self.assertIn(act_name, body)

    @test.attr(type='negative')
    def test_get_nonexistent_action(self):
        self.assertRaises(exceptions.NotFound,
                          self.client.get_object,
                          'actions', 'nonexist')

    @test.attr(type='negative')
    def test_double_creation(self):
        self.client.create_action('action_v2.yaml')

        self.assertRaises(exceptions.Conflict,
                          self.client.create_action,
                          'action_v2.yaml')

    @test.attr(type='negative')
    def test_create_action_invalid_def(self):
        self.assertRaises(exceptions.ServerFault,
                          self.client.create_action, 'wb_v2.yaml')

    @test.attr(type='negative')
    def test_update_action_invalid_def(self):
        self.assertRaises(exceptions.ServerFault,
                          self.client.update_request,
                          'actions', 'wb_v2.yaml')

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


class TasksTestsV2(base.TestCase):

    _service = 'workflowv2'

    def setUp(self):
        super(TasksTestsV2, self).setUp()

        _, body = self.client.create_workflow('wf_v2.yaml')
        self.direct_wf = body['workflows'][0]['name']
        _, execution = self.client.create_execution(self.direct_wf)

    def tearDown(self):
        for wf in self.client.workflows:
            self.client.delete_obj('workflows', wf)
        self.client.workflows = []

        super(TasksTestsV2, self).tearDown()

    @test.attr(type='smoke')
    def test_get_tasks_list(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)
        self.assertNotEmpty(body['tasks'])

    @test.attr(type='sanity')
    def test_get_task(self):
        resp, body = self.client.get_list_obj('tasks')

        self.assertEqual(200, resp.status)
        self.assertEqual(self.direct_wf, body['tasks'][-1]['workflow_name'])
