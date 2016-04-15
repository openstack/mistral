# Copyright 2016 - Catalyst IT Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import uuid

import mock
from oslo_config import cfg

from mistral.db.v2 import api as db_api
from mistral.services import security
from mistral.tests.unit.api import base

GET_PROJECT_PATH = 'mistral.services.security.get_project_id'

WF_DEFINITION = {
    'name': 'test_wf',
    'definition': 'empty',
    'spec': {},
    'tags': ['mc'],
    'scope': 'private',
    'project_id': security.get_project_id(),
    'trust_id': '1234'
}

WORKFLOW_MEMBER_PENDING = {
    'member_id': '11-22-33',
    'project_id': '<default-project>',
    'resource_type': 'workflow',
    'status': 'pending'
}

WORKFLOW_MEMBER_ACCEPTED = {}

MEMBER_URL = None


class TestMembersController(base.APITest):
    def setUp(self):
        super(TestMembersController, self).setUp()

        wf = db_api.create_workflow_definition(WF_DEFINITION)

        global MEMBER_URL, WORKFLOW_MEMBER_ACCEPTED

        MEMBER_URL = '/v2/workflows/%s/members' % wf.id

        WORKFLOW_MEMBER_PENDING['resource_id'] = wf.id

        WORKFLOW_MEMBER_ACCEPTED = copy.deepcopy(WORKFLOW_MEMBER_PENDING)
        WORKFLOW_MEMBER_ACCEPTED['status'] = 'accepted'

        cfg.CONF.set_default('auth_enable', True, group='pecan')

    def test_membership_api_without_auth(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')

        resp = self.app.get(MEMBER_URL, expect_errors=True)

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            "Resource sharing feature can only be supported with "
            "authentication enabled",
            resp.body.decode()
        )

    @mock.patch('mistral.context.AuthHook.before')
    def test_create_resource_member(self, auth_mock):
        # Workflow owner shares workflow to another tenant.
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)
        self._assert_dict_contains_subset(WORKFLOW_MEMBER_PENDING, resp.json)

    @mock.patch('mistral.context.AuthHook.before')
    def test_create_membership_nonexistent_wf(self, auth_mock):
        nonexistent_wf_id = str(uuid.uuid4())

        resp = self.app.post_json(
            '/v2/workflows/%s/members' % nonexistent_wf_id,
            {'member_id': '11-22-33'},
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch('mistral.context.AuthHook.before')
    def test_create_duplicate_membership(self, auth_mock):
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        resp = self.app.post_json(
            MEMBER_URL,
            {'member_id': '11-22-33'},
            expect_errors=True
        )

        self.assertEqual(409, resp.status_int)
        self.assertIn("Duplicate entry for ResourceMember", resp.body.decode())

    @mock.patch('mistral.context.AuthHook.before')
    def test_create_membership_public_wf(self, auth_mock):
        WF_DEFINITION_PUBLIC = copy.deepcopy(WF_DEFINITION)
        WF_DEFINITION_PUBLIC['name'] = 'test_wf1'
        WF_DEFINITION_PUBLIC['scope'] = 'public'

        wf_public = db_api.create_workflow_definition(WF_DEFINITION_PUBLIC)

        resp = self.app.post_json(
            '/v2/workflows/%s/members' % wf_public.id,
            {'member_id': '11-22-33'},
            expect_errors=True
        )

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            "Only private resource could be shared",
            resp.body.decode()
        )

    @mock.patch('mistral.context.AuthHook.before')
    def test_create_membership_untransferable(self, auth_mock):
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        # Using mock to switch to another tenant.
        get_mock = mock.MagicMock(return_value='11-22-33')

        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.post_json(
                MEMBER_URL,
                {'member_id': 'other_tenant'},
                expect_errors=True
            )

        self.assertEqual(404, resp.status_int)

    @mock.patch('mistral.context.AuthHook.before')
    def test_get_other_memberships(self, auth_mock):
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        # Using mock to switch to another tenant.
        get_mock = mock.MagicMock(return_value='other_tenant')

        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.get(MEMBER_URL)

        self.assertEqual(200, resp.status_int)
        self.assertEqual(0, len(resp.json['members']))

    @mock.patch('mistral.context.AuthHook.before')
    def test_get_memberships_nonexistent_wf(self, auth_mock):
        nonexistent_wf_id = str(uuid.uuid4())

        resp = self.app.get(
            '/v2/workflows/%s/members' % nonexistent_wf_id,
        )

        self.assertEqual(200, resp.status_int)
        self.assertEqual(0, len(resp.json['members']))

    @mock.patch('mistral.context.AuthHook.before')
    def test_get_resource_memberips(self, auth_mock):
        # Workflow owner shares workflow to another tenant.
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)
        self._assert_dict_contains_subset(WORKFLOW_MEMBER_PENDING, resp.json)

        # Workflow owner queries the workflow members.
        resp = self.app.get(MEMBER_URL)

        self.assertEqual(200, resp.status_int)
        self.assertEqual(1, len(resp.json['members']))
        self._assert_dict_contains_subset(
            WORKFLOW_MEMBER_PENDING,
            resp.json['members'][0]
        )

        # Workflow owner queries the exact workflow member.
        resp = self.app.get('%s/11-22-33' % MEMBER_URL)

        self.assertEqual(200, resp.status_int)
        self._assert_dict_contains_subset(
            WORKFLOW_MEMBER_PENDING,
            resp.json
        )

    @mock.patch('mistral.context.AuthHook.before')
    def test_get_other_membership(self, auth_mock):
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        # Using mock to switch to another tenant.
        get_mock = mock.MagicMock(return_value='other_tenant')

        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.get(
                '%s/11-22-33' % MEMBER_URL,
                expect_errors=True
            )

        self.assertEqual(404, resp.status_int)

    @mock.patch('mistral.context.AuthHook.before')
    def test_update_membership(self, auth_mock):
        # Workflow owner shares workflow to another tenant.
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        # Using mock to switch to another tenant.
        get_mock = mock.MagicMock(return_value='11-22-33')

        # Tenant accepts the workflow shared to him.
        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.put_json(
                '%s/11-22-33' % MEMBER_URL,
                {'status': 'accepted'}
            )

        self.assertEqual(200, resp.status_int)
        self._assert_dict_contains_subset(
            WORKFLOW_MEMBER_ACCEPTED,
            resp.json
        )

        # Tenant queries exact member of workflow shared to him.
        # (status=accepted).
        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.get('%s/11-22-33' % MEMBER_URL)

        self.assertEqual(200, resp.status_int)
        self._assert_dict_contains_subset(
            WORKFLOW_MEMBER_ACCEPTED,
            resp.json
        )

        # Workflow owner queries the exact workflow member.
        # (status=accepted).
        resp = self.app.get('%s/11-22-33' % MEMBER_URL)

        self.assertEqual(200, resp.status_int)
        self._assert_dict_contains_subset(
            WORKFLOW_MEMBER_ACCEPTED,
            resp.json
        )

    @mock.patch('mistral.context.AuthHook.before')
    def test_update_membership_invalid_status(self, auth_mock):
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        # Using mock to switch to another tenant.
        get_mock = mock.MagicMock(return_value='11-22-33')

        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.put_json(
                '%s/11-22-33' % MEMBER_URL,
                {'status': 'invalid'},
                expect_errors=True
            )

        self.assertEqual(400, resp.status_int)
        self.assertIn(
            "Invalid input",
            resp.body.decode()
        )

    @mock.patch('mistral.context.AuthHook.before')
    def test_update_membership_not_shared_user(self, auth_mock):
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        resp = self.app.put_json(
            '%s/11-22-33' % MEMBER_URL,
            {'status': 'accepted'},
            expect_errors=True
        )

        self.assertEqual(404, resp.status_int)

    @mock.patch('mistral.context.AuthHook.before')
    def test_delete_membership(self, auth_mock):
        # Workflow owner shares workflow to another tenant.
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        # Workflow owner deletes the exact workflow member.
        resp = self.app.delete('%s/11-22-33' % MEMBER_URL)

        self.assertEqual(204, resp.status_int)

        # Workflow owner queries the workflow members.
        resp = self.app.get(MEMBER_URL)

        self.assertEqual(200, resp.status_int)
        self.assertEqual(0, len(resp.json['members']))

        # Using mock to switch to another tenant.
        get_mock = mock.MagicMock(return_value='11-22-33')

        # Tenant queries members of workflow shared to him, after deletion.
        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.get(MEMBER_URL)

        self.assertEqual(200, resp.status_int)
        self.assertEqual(0, len(resp.json['members']))

    @mock.patch('mistral.context.AuthHook.before')
    def test_delete_membership_not_owner(self, auth_mock):
        resp = self.app.post_json(MEMBER_URL, {'member_id': '11-22-33'})

        self.assertEqual(201, resp.status_int)

        # Using mock to switch to another tenant.
        get_mock = mock.MagicMock(return_value='11-22-33')

        with mock.patch(GET_PROJECT_PATH, get_mock):
            resp = self.app.delete(
                '%s/11-22-33' % MEMBER_URL,
                expect_errors=True
            )

        self.assertEqual(404, resp.status_int)
