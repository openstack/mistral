# Copyright 2015 - Mirantis, Inc.
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

# TODO(rakhmerov): Add checks for timestamps.

import copy
import datetime

from oslo_config import cfg

from mistral import context as auth_context
from mistral.db.v2.sqlalchemy import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral import exceptions as exc
from mistral.services import security
from mistral.tests.unit import base as test_base
from mistral.utils import filter_utils


user_context = test_base.get_context(default=False)

WORKBOOKS = [
    {
        'name': 'my_workbook1',
        'definition': 'empty',
        'spec': {},
        'tags': ['mc'],
        'scope': 'public',
        'updated_at': None,
        'project_id': '1233',
        'trust_id': '1234'
    },
    {
        'name': 'my_workbook2',
        'description': 'my description',
        'definition': 'empty',
        'spec': {},
        'tags': ['mc'],
        'scope': 'private',
        'updated_at': None,
        'project_id': '1233',
        'trust_id': '12345'
    },
]


class SQLAlchemyTest(test_base.DbTestCase):
    def setUp(self):
        super(SQLAlchemyTest, self).setUp()

        cfg.CONF.set_default('auth_enable', True, group='pecan')
        self.addCleanup(cfg.CONF.set_default, 'auth_enable', False,
                        group='pecan')


class WorkbookTest(SQLAlchemyTest):
    def test_create_and_get_and_load_workbook(self):
        created = db_api.create_workbook(WORKBOOKS[0])

        fetched = db_api.get_workbook(created['name'])

        self.assertEqual(created, fetched)

        fetched = db_api.load_workbook(created.name)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_workbook("not-existing-wb"))

    def test_create_workbook_duplicate_without_auth(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')
        db_api.create_workbook(WORKBOOKS[0])

        self.assertRaises(
            exc.DBDuplicateEntryError,
            db_api.create_workbook,
            WORKBOOKS[0]
        )

    def test_update_workbook(self):
        created = db_api.create_workbook(WORKBOOKS[0])

        self.assertIsNone(created.updated_at)

        updated = db_api.update_workbook(
            created.name,
            {'definition': 'my new definition'}
        )

        self.assertEqual('my new definition', updated.definition)

        fetched = db_api.get_workbook(created['name'])

        self.assertEqual(updated, fetched)
        self.assertIsNotNone(fetched.updated_at)

    def test_create_or_update_workbook(self):
        name = WORKBOOKS[0]['name']

        self.assertIsNone(db_api.load_workbook(name))

        created = db_api.create_or_update_workbook(
            name,
            WORKBOOKS[0]
        )

        self.assertIsNotNone(created)
        self.assertIsNotNone(created.name)

        updated = db_api.create_or_update_workbook(
            created.name,
            {'definition': 'my new definition'}
        )

        self.assertEqual('my new definition', updated.definition)
        self.assertEqual(
            'my new definition',
            db_api.load_workbook(updated.name).definition
        )

        fetched = db_api.get_workbook(created.name)

        self.assertEqual(updated, fetched)

    def test_get_workbooks(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        fetched = db_api.get_workbooks()

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_workbooks_by_equal_value(self):
        db_api.create_workbook(WORKBOOKS[0])

        created = db_api.create_workbook(WORKBOOKS[1])
        _filter = filter_utils.create_or_update_filter(
            'name',
            created.name,
            'eq'
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created, fetched[0])

    def test_filter_workbooks_by_not_equal_value(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'name',
            created0.name,
            'neq'
        )

        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_filter_workbooks_by_greater_than_value(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created0['created_at'],
            'gt'
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_filter_workbooks_by_greater_than_equal_value(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created0['created_at'],
            'gte'
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_workbooks_by_less_than_value(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created1['created_at'],
            'lt'
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_filter_workbooks_by_less_than_equal_value(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created1['created_at'],
            'lte'
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_workbooks_by_values_in_list(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])

        db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at']],
            'in'
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_filter_workbooks_by_values_notin_list(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at']],
            'nin'
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_filter_workbooks_by_multiple_columns(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at'], created1['created_at']],
            'in'
        )
        _filter = filter_utils.create_or_update_filter(
            'name',
            'my_workbook2',
            'eq',
            _filter
        )
        fetched = db_api.get_workbooks(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_delete_workbook(self):
        created = db_api.create_workbook(WORKBOOKS[0])

        fetched = db_api.get_workbook(created.name)

        self.assertEqual(created, fetched)

        db_api.delete_workbook(created.name)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workbook,
            created.name
        )

    def test_workbooks_in_two_projects(self):
        created = db_api.create_workbook(WORKBOOKS[1])
        fetched = db_api.get_workbooks()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created, fetched[0])

        # Create a new user.
        auth_context.set_ctx(test_base.get_context(default=False))

        created = db_api.create_workbook(WORKBOOKS[1])
        fetched = db_api.get_workbooks()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created, fetched[0])

    def test_workbook_private(self):
        # Create a workbook(scope=private) as under one project
        # then make sure it's NOT visible for other projects.
        created1 = db_api.create_workbook(WORKBOOKS[1])

        fetched = db_api.get_workbooks()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

        # Create a new user.
        auth_context.set_ctx(test_base.get_context(default=False))

        fetched = db_api.get_workbooks()

        self.assertEqual(0, len(fetched))

    def test_workbook_public(self):
        # Create a workbook(scope=public) as under one project
        # then make sure it's visible for other projects.
        created0 = db_api.create_workbook(WORKBOOKS[0])

        fetched = db_api.get_workbooks()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

        # Assert that the project_id stored is actually the context's
        # project_id not the one given.
        self.assertEqual(created0.project_id, auth_context.ctx().project_id)
        self.assertNotEqual(WORKBOOKS[0]['project_id'],
                            auth_context.ctx().project_id)

        # Create a new user.
        auth_context.set_ctx(test_base.get_context(default=False))

        fetched = db_api.get_workbooks()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual('public', created0.scope)

    def test_workbook_repr(self):
        s = db_api.create_workbook(WORKBOOKS[0]).__repr__()

        self.assertIn('Workbook ', s)
        self.assertIn("'name': 'my_workbook1'", s)


WF_DEFINITIONS = [
    {
        'name': 'my_wf1',
        'definition': 'empty',
        'spec': {},
        'tags': ['mc'],
        'scope': 'public',
        'project_id': '1233',
        'trust_id': '1234'
    },
    {
        'name': 'my_wf2',
        'definition': 'empty',
        'spec': {},
        'tags': ['mc'],
        'scope': 'private',
        'project_id': '1233',
        'trust_id': '12345'
    },
]


CRON_TRIGGER = {
    'name': 'trigger1',
    'pattern': '* * * * *',
    'workflow_name': 'my_wf1',
    'workflow_id': None,
    'workflow_input': {},
    'next_execution_time':
    datetime.datetime.now() + datetime.timedelta(days=1),
    'remaining_executions': 42,
    'scope': 'private',
    'project_id': '<default-project>'
}


class WorkflowDefinitionTest(SQLAlchemyTest):
    def test_create_and_get_and_load_workflow_definition(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        fetched = db_api.get_workflow_definition(created.name)

        self.assertEqual(created, fetched)

        fetched = db_api.load_workflow_definition(created.name)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_workflow_definition("not-existing-wf"))

    def test_get_workflow_definition_with_uuid(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        fetched = db_api.get_workflow_definition(created.id)

        self.assertEqual(created, fetched)

    def test_filter_workflow_definitions_by_equal_value(self):
        db_api.create_workbook(WF_DEFINITIONS[0])

        created = db_api.create_workflow_definition(WF_DEFINITIONS[1])
        _filter = filter_utils.create_or_update_filter(
            'name',
            created.name,
            'eq'
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created, fetched[0])

    def test_filter_workflow_definition_by_not_equal_valiue(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'name',
            created0.name,
            'neq'
        )

        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_filter_workflow_definition_by_greater_than_value(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created0['created_at'],
            'gt'
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_filter_workflow_definition_by_greater_than_equal_value(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created0['created_at'],
            'gte'
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_workflow_definition_by_less_than_value(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created1['created_at'],
            'lt'
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_filter_workflow_definition_by_less_than_equal_value(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created1['created_at'],
            'lte'
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_workflow_definition_by_values_in_list(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at']],
            'in'
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_filter_workflow_definition_by_values_notin_list(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at']],
            'nin'
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_filter_workflow_definition_by_multiple_columns(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at'], created1['created_at']],
            'in'
        )
        _filter = filter_utils.create_or_update_filter(
            'name',
            'my_wf2',
            'eq',
            _filter
        )
        fetched = db_api.get_workflow_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

    def test_create_workflow_definition_duplicate_without_auth(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')
        db_api.create_workflow_definition(WF_DEFINITIONS[0])

        self.assertRaises(
            exc.DBDuplicateEntryError,
            db_api.create_workflow_definition,
            WF_DEFINITIONS[0]
        )

    def test_update_workflow_definition(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        self.assertIsNone(created.updated_at)

        # Update workflow using workflow name as identifier.
        updated = db_api.update_workflow_definition(
            created['name'],
            {'definition': 'my new definition', 'scope': 'private'}
        )

        self.assertEqual('my new definition', updated.definition)

        fetched = db_api.get_workflow_definition(created.name)

        self.assertEqual(updated, fetched)
        self.assertIsNotNone(fetched.updated_at)

        # Update workflow using workflow uuid as identifier.
        updated = db_api.update_workflow_definition(
            created['id'],
            {
                'name': 'updated_name',
                'definition': 'my new definition',
                'scope': 'private'
            }
        )

        self.assertEqual('updated_name', updated.name)
        self.assertEqual('my new definition', updated.definition)

        fetched = db_api.get_workflow_definition(created['id'])

        self.assertEqual(updated, fetched)
        self.assertIsNotNone(fetched.updated_at)

    def test_update_other_project_workflow_definition(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        # Switch to another project.
        auth_context.set_ctx(test_base.get_context(default=False))

        self.assertRaises(
            exc.NotAllowedException,
            db_api.update_workflow_definition,
            created.name,
            {'definition': 'my new definition', 'scope': 'private'}
        )

    def test_create_or_update_workflow_definition(self):
        name = WF_DEFINITIONS[0]['name']

        self.assertIsNone(db_api.load_workflow_definition(name))

        created = db_api.create_or_update_workflow_definition(
            name,
            WF_DEFINITIONS[0]
        )

        self.assertIsNotNone(created)
        self.assertIsNotNone(created.name)

        updated = db_api.create_or_update_workflow_definition(
            created.name,
            {'definition': 'my new definition', 'scope': 'private'}
        )

        self.assertEqual('my new definition', updated.definition)
        self.assertEqual(
            'my new definition',
            db_api.load_workflow_definition(updated.name).definition
        )

        fetched = db_api.get_workflow_definition(created.name)

        self.assertEqual(updated, fetched)

    def test_update_wf_scope_cron_trigger_associated_in_diff_tenant(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        # Create a new user.
        auth_context.set_ctx(test_base.get_context(default=False))

        cron_trigger = copy.copy(CRON_TRIGGER)
        cron_trigger['workflow_id'] = created.id
        db_api.create_cron_trigger(cron_trigger)

        auth_context.set_ctx(test_base.get_context(default=True))

        self.assertRaises(
            exc.NotAllowedException,
            db_api.update_workflow_definition,
            created['name'],
            {'scope': 'private'}
        )

    def test_update_wf_scope_event_trigger_associated_in_diff_tenant(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        # Switch to another user.
        auth_context.set_ctx(test_base.get_context(default=False))

        event_trigger = copy.copy(EVENT_TRIGGERS[0])
        event_trigger.update({'workflow_id': created.id})

        db_api.create_event_trigger(event_trigger)

        # Switch back.
        auth_context.set_ctx(test_base.get_context(default=True))

        self.assertRaises(
            exc.NotAllowedException,
            db_api.update_workflow_definition,
            created.id,
            {'scope': 'private'}
        )

    def test_update_wf_scope_event_trigger_associated_in_same_tenant(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        event_trigger = copy.copy(EVENT_TRIGGERS[0])
        event_trigger.update({'workflow_id': created.id})

        db_api.create_event_trigger(event_trigger)

        updated = db_api.update_workflow_definition(
            created.id,
            {'scope': 'private'}
        )

        self.assertEqual('private', updated.scope)

    def test_update_wf_scope_cron_trigger_associated_in_same_tenant(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        cron_trigger = copy.copy(CRON_TRIGGER)
        cron_trigger.update({'workflow_id': created.id})

        db_api.create_cron_trigger(cron_trigger)

        updated = db_api.update_workflow_definition(
            created['name'],
            {'scope': 'private'}
        )

        self.assertEqual('private', updated.scope)

    def test_get_workflow_definitions(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        fetched0 = db_api.load_workflow_definition(created0.name)
        fetched1 = db_api.load_workflow_definition(created1.name)

        self.assertEqual(security.get_project_id(), fetched0.project_id)
        self.assertEqual(security.get_project_id(), fetched1.project_id)

        fetched = db_api.get_workflow_definitions()

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_delete_workflow_definition(self):
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        fetched0 = db_api.get_workflow_definition(created0.name)
        fetched1 = db_api.get_workflow_definition(created1.id)

        self.assertEqual(created0, fetched0)
        self.assertEqual(created1, fetched1)

        for identifier in [created0.name, created1.id]:
            db_api.delete_workflow_definition(identifier)

            self.assertRaises(
                exc.DBEntityNotFoundError,
                db_api.get_workflow_definition,
                identifier
            )

    def test_delete_workflow_definition_has_event_trigger(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        event_trigger = copy.copy(EVENT_TRIGGERS[0])
        event_trigger['workflow_id'] = created.id

        trigger = db_api.create_event_trigger(event_trigger)

        self.assertEqual(trigger.workflow_id, created.id)

        self.assertRaises(
            exc.DBError,
            db_api.delete_workflow_definition,
            created.id
        )

    def test_delete_other_project_workflow_definition(self):
        created = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        # Switch to another project.
        auth_context.set_ctx(test_base.get_context(default=False))

        self.assertRaises(
            exc.NotAllowedException,
            db_api.delete_workflow_definition,
            created.name
        )

    def test_workflow_definition_private(self):
        # Create a workflow(scope=private) as under one project
        # then make sure it's NOT visible for other projects.
        created1 = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        fetched = db_api.get_workflow_definitions()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

        # Create a new user.
        auth_context.set_ctx(test_base.get_context(default=False))

        fetched = db_api.get_workflow_definitions()

        self.assertEqual(0, len(fetched))

    def test_workflow_definition_public(self):
        # Create a workflow(scope=public) as under one project
        # then make sure it's visible for other projects.
        created0 = db_api.create_workflow_definition(WF_DEFINITIONS[0])

        fetched = db_api.get_workflow_definitions()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

        # Assert that the project_id stored is actually the context's
        # project_id not the one given.
        self.assertEqual(created0.project_id, auth_context.ctx().project_id)
        self.assertNotEqual(
            WF_DEFINITIONS[0]['project_id'],
            auth_context.ctx().project_id
        )

        # Create a new user.
        auth_context.set_ctx(test_base.get_context(default=False))

        fetched = db_api.get_workflow_definitions()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual('public', fetched[0].scope)

    def test_workflow_definition_repr(self):
        s = db_api.create_workflow_definition(WF_DEFINITIONS[0]).__repr__()

        self.assertIn('WorkflowDefinition ', s)
        self.assertIn("'name': 'my_wf1'", s)


ACTION_DEFINITIONS = [
    {
        'name': 'action1',
        'description': 'Action #1',
        'is_system': True,
        'action_class': 'mypackage.my_module.Action1',
        'attributes': None,
        'project_id': '<default-project>'
    },
    {
        'name': 'action2',
        'description': 'Action #2',
        'is_system': True,
        'action_class': 'mypackage.my_module.Action2',
        'attributes': None,
        'project_id': '<default-project>'
    },
    {
        'name': 'action3',
        'description': 'Action #3',
        'is_system': False,
        'tags': ['mc', 'abc'],
        'action_class': 'mypackage.my_module.Action3',
        'attributes': None,
        'project_id': '<default-project>'
    },
]


class ActionDefinitionTest(SQLAlchemyTest):
    def setUp(self):
        super(ActionDefinitionTest, self).setUp()

        db_api.delete_action_definitions()

    def test_create_and_get_and_load_action_definition(self):
        created = db_api.create_action_definition(ACTION_DEFINITIONS[0])

        fetched = db_api.get_action_definition(created.name)

        self.assertEqual(created, fetched)

        fetched = db_api.load_action_definition(created.name)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_action_definition("not-existing-id"))

    def test_get_action_definition_with_uuid(self):
        created = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        fetched = db_api.get_action_definition(created.id)

        self.assertEqual(created, fetched)

    def test_create_action_definition_duplicate_without_auth(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')
        db_api.create_action_definition(ACTION_DEFINITIONS[0])

        self.assertRaises(
            exc.DBDuplicateEntryError,
            db_api.create_action_definition,
            ACTION_DEFINITIONS[0]
        )

    def test_filter_action_definitions_by_equal_value(self):
        db_api.create_action_definition(ACTION_DEFINITIONS[0])
        db_api.create_action_definition(ACTION_DEFINITIONS[1])

        created2 = db_api.create_action_definition(ACTION_DEFINITIONS[2])
        _filter = filter_utils.create_or_update_filter(
            'is_system',
            False,
            'eq'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created2, fetched[0])

    def test_filter_action_definitions_by_not_equal_value(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])

        db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'is_system',
            False,
            'neq'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_action_definitions_by_greater_than_value(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])
        created2 = db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created0['created_at'],
            'gt'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created1, fetched[0])
        self.assertEqual(created2, fetched[1])

    def test_filter_action_definitions_by_greater_than_equal_value(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])
        created2 = db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created0['created_at'],
            'gte'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(3, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])
        self.assertEqual(created2, fetched[2])

    def test_filter_action_definitions_by_less_than_value(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])
        created2 = db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created2['created_at'],
            'lt'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_action_definitions_by_less_than_equal_value(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])
        created2 = db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            created2['created_at'],
            'lte'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(3, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])
        self.assertEqual(created2, fetched[2])

    def test_filter_action_definitions_by_values_in_list(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])

        db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at'], created1['created_at']],
            'in'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_filter_action_definitions_by_values_notin_list(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])
        created2 = db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at'], created1['created_at']],
            'nin'
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(1, len(fetched))
        self.assertEqual(created2, fetched[0])

    def test_filter_action_definitions_by_multiple_columns(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])

        db_api.create_action_definition(ACTION_DEFINITIONS[2])

        _filter = filter_utils.create_or_update_filter(
            'created_at',
            [created0['created_at'], created1['created_at']],
            'in'
        )
        _filter = filter_utils.create_or_update_filter(
            'is_system',
            True,
            'neq',
            _filter
        )
        fetched = db_api.get_action_definitions(**_filter)

        self.assertEqual(0, len(fetched))

    def test_update_action_definition_with_name(self):
        created = db_api.create_action_definition(ACTION_DEFINITIONS[0])

        self.assertIsNone(created.updated_at)

        updated = db_api.update_action_definition(
            created.name,
            {'description': 'my new desc'}
        )

        self.assertEqual('my new desc', updated.description)

        fetched = db_api.get_action_definition(created.name)

        self.assertEqual(updated, fetched)
        self.assertIsNotNone(fetched.updated_at)

    def test_update_action_definition_with_uuid(self):
        created = db_api.create_action_definition(ACTION_DEFINITIONS[0])

        self.assertIsNone(created.updated_at)

        updated = db_api.update_action_definition(
            created.id,
            {'description': 'my new desc'}
        )

        self.assertEqual('my new desc', updated.description)

        fetched = db_api.get_action_definition(created.id)

        self.assertEqual(updated, fetched)

    def test_create_or_update_action_definition(self):
        name = 'not-existing-id'

        self.assertIsNone(db_api.load_action_definition(name))

        created = db_api.create_or_update_action_definition(
            name,
            ACTION_DEFINITIONS[0]
        )

        self.assertIsNotNone(created)
        self.assertIsNotNone(created.name)

        updated = db_api.create_or_update_action_definition(
            created.name,
            {'description': 'my new desc'}
        )

        self.assertEqual('my new desc', updated.description)
        self.assertEqual(
            'my new desc',
            db_api.load_action_definition(updated.name).description
        )

        fetched = db_api.get_action_definition(created.name)

        self.assertEqual(updated, fetched)

    def test_get_action_definitions(self):
        created0 = db_api.create_action_definition(ACTION_DEFINITIONS[0])
        created1 = db_api.create_action_definition(ACTION_DEFINITIONS[1])

        fetched = db_api.get_action_definitions(is_system=True)

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_delete_action_definition_with_name(self):
        created = db_api.create_action_definition(ACTION_DEFINITIONS[0])

        fetched = db_api.get_action_definition(created.name)

        self.assertEqual(created, fetched)

        db_api.delete_action_definition(created.name)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_action_definition,
            created.name
        )

    def test_delete_action_definition_with_uuid(self):
        created = db_api.create_action_definition(ACTION_DEFINITIONS[0])

        fetched = db_api.get_action_definition(created.id)

        self.assertEqual(created, fetched)

        db_api.delete_action_definition(created.id)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_action_definition,
            created.id
        )

    def test_action_definition_repr(self):
        s = db_api.create_action_definition(ACTION_DEFINITIONS[0]).__repr__()

        self.assertIn('ActionDefinition ', s)
        self.assertIn("'description': 'Action #1'", s)
        self.assertIn("'name': 'action1'", s)


ACTION_EXECS = [
    {
        'spec': None,
        'state': 'IDLE',
        'state_info': "Running...",
        'created_at': None,
        'updated_at': None,
        'task_id': None,
        'tags': [],
        'accepted': True,
        'output': {"result": "value"}
    },
    {
        'spec': None,
        'state': 'ERROR',
        'state_info': "Failed due to some reason...",
        'created_at': None,
        'updated_at': None,
        'task_id': None,
        'tags': ['deployment'],
        'accepted': False,
        'output': {"result": "value"}
    }
]


class ActionExecutionTest(SQLAlchemyTest):
    def test_create_and_get_and_load_action_execution(self):
        created = db_api.create_action_execution(ACTION_EXECS[0])

        fetched = db_api.get_action_execution(created.id)

        self.assertEqual(created, fetched)

        fetched = db_api.load_action_execution(created.id)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_action_execution("not-existing-id"))

    def test_update_action_execution(self):
        with db_api.transaction():
            created = db_api.create_action_execution(ACTION_EXECS[0])

            self.assertIsNone(created.updated_at)

            updated = db_api.update_action_execution(
                created.id,
                {'state': 'RUNNING', 'state_info': "Running..."}
            )

            self.assertEqual('RUNNING', updated.state)
            self.assertEqual(
                'RUNNING',
                db_api.load_action_execution(updated.id).state
            )

            fetched = db_api.get_action_execution(created.id)

            self.assertEqual(updated, fetched)
            self.assertIsNotNone(fetched.updated_at)

    def test_create_or_update_action_execution(self):
        id = 'not-existing-id'

        self.assertIsNone(db_api.load_action_execution(id))

        created = db_api.create_or_update_action_execution(id, ACTION_EXECS[0])

        self.assertIsNotNone(created)
        self.assertIsNotNone(created.id)

        with db_api.transaction():
            updated = db_api.create_or_update_action_execution(
                created.id,
                {'state': 'RUNNING'}
            )

            self.assertEqual('RUNNING', updated.state)
            self.assertEqual(
                'RUNNING',
                db_api.load_action_execution(updated.id).state
            )

            fetched = db_api.get_action_execution(created.id)

            self.assertEqual(updated, fetched)

    def test_get_action_executions(self):
        created0 = db_api.create_action_execution(WF_EXECS[0])
        db_api.create_action_execution(ACTION_EXECS[1])

        fetched = db_api.get_action_executions(
            state=WF_EXECS[0]['state']
        )

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_delete_action_execution(self):
        created = db_api.create_action_execution(ACTION_EXECS[0])

        fetched = db_api.get_action_execution(created.id)

        self.assertEqual(created, fetched)

        db_api.delete_action_execution(created.id)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_action_execution,
            created.id
        )

    def test_delete_other_tenant_action_execution(self):
        created = db_api.create_action_execution(ACTION_EXECS[0])

        # Create a new user.
        auth_context.set_ctx(test_base.get_context(default=False))

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.delete_action_execution,
            created.id
        )

    def test_trim_status_info(self):
        created = db_api.create_action_execution(ACTION_EXECS[0])

        self.assertIsNone(created.updated_at)

        updated = db_api.update_action_execution(
            created.id,
            {'state': 'FAILED', 'state_info': ".." * 65536}
        )

        self.assertEqual('FAILED', updated.state)
        state_info = db_api.load_action_execution(updated.id).state_info
        self.assertEqual(
            65535,
            len(state_info)
        )

    def test_action_execution_repr(self):
        s = db_api.create_action_execution(ACTION_EXECS[0]).__repr__()

        self.assertIn('ActionExecution ', s)
        self.assertIn("'state': 'IDLE'", s)
        self.assertIn("'state_info': 'Running...'", s)
        self.assertIn("'accepted': True", s)


WF_EXECS = [
    {
        'spec': {},
        'start_params': {'task': 'my_task1'},
        'state': 'IDLE',
        'state_info': "Running...",
        'created_at': None,
        'updated_at': None,
        'context': None,
        'task_id': None,
        'trust_id': None,
        'description': None,
        'output': None
    },
    {
        'spec': {},
        'start_params': {'task': 'my_task1'},
        'state': 'RUNNING',
        'state_info': "Running...",
        'created_at': None,
        'updated_at': None,
        'context': {'image_id': '123123'},
        'task_id': None,
        'trust_id': None,
        'description': None,
        'output': None
    }
]


class WorkflowExecutionTest(SQLAlchemyTest):
    def test_create_and_get_and_load_workflow_execution(self):
        created = db_api.create_workflow_execution(WF_EXECS[0])

        fetched = db_api.get_workflow_execution(created.id)

        self.assertEqual(created, fetched)

        fetched = db_api.load_workflow_execution(created.id)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_workflow_execution("not-existing-id"))

    def test_update_workflow_execution(self):
        with db_api.transaction():
            created = db_api.create_workflow_execution(WF_EXECS[0])

            self.assertIsNone(created.updated_at)

            updated = db_api.update_workflow_execution(
                created.id,
                {'state': 'RUNNING', 'state_info': "Running..."}
            )

            self.assertEqual('RUNNING', updated.state)
            self.assertEqual(
                'RUNNING',
                db_api.load_workflow_execution(updated.id).state
            )

            fetched = db_api.get_workflow_execution(created.id)

            self.assertEqual(updated, fetched)
            self.assertIsNotNone(fetched.updated_at)

    def test_create_or_update_workflow_execution(self):
        id = 'not-existing-id'

        self.assertIsNone(db_api.load_workflow_execution(id))

        with db_api.transaction():
            created = db_api.create_or_update_workflow_execution(
                id,
                WF_EXECS[0]
            )

            self.assertIsNotNone(created)
            self.assertIsNotNone(created.id)

            updated = db_api.create_or_update_workflow_execution(
                created.id,
                {'state': 'RUNNING'}
            )

            self.assertEqual('RUNNING', updated.state)
            self.assertEqual(
                'RUNNING',
                db_api.load_workflow_execution(updated.id).state
            )

            fetched = db_api.get_workflow_execution(created.id)

            self.assertEqual(updated, fetched)

    def test_get_workflow_executions(self):
        created0 = db_api.create_workflow_execution(WF_EXECS[0])
        db_api.create_workflow_execution(WF_EXECS[1])

        fetched = db_api.get_workflow_executions(
            state=WF_EXECS[0]['state']
        )

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_delete_workflow_execution(self):
        created = db_api.create_workflow_execution(WF_EXECS[0])

        fetched = db_api.get_workflow_execution(created.id)

        self.assertEqual(created, fetched)

        db_api.delete_workflow_execution(created.id)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workflow_execution,
            created.id
        )

    def test_trim_status_info(self):
        created = db_api.create_workflow_execution(WF_EXECS[0])

        self.assertIsNone(created.updated_at)

        updated = db_api.update_workflow_execution(
            created.id,
            {'state': 'FAILED', 'state_info': ".." * 65536}
        )

        self.assertEqual('FAILED', updated.state)
        state_info = db_api.load_workflow_execution(updated.id).state_info
        self.assertEqual(
            65535,
            len(state_info)
        )

    def test_task_executions(self):
        # Add an associated object into collection.
        with db_api.transaction():
            wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

            self.assertEqual(0, len(wf_ex.task_executions))

            wf_ex.task_executions.append(
                db_models.TaskExecution(**TASK_EXECS[0])
            )

        # Make sure task execution has been saved.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertIsNotNone(wf_ex)

            self.assertEqual(1, len(wf_ex.task_executions))

            task_ex = wf_ex.task_executions[0]

            self.assertEqual(TASK_EXECS[0]['name'], task_ex.name)

        self.assertEqual(1, len(db_api.get_workflow_executions()))
        self.assertEqual(1, len(db_api.get_task_executions()))

        # Remove task execution from collection.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            del wf_ex.task_executions[:]

        # Make sure task execution has been removed.
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex.id)

            self.assertEqual(0, len(wf_ex.task_executions))
            self.assertIsNone(db_api.load_task_execution(task_ex.id))

    def test_workflow_execution_repr(self):
        s = db_api.create_workflow_execution(WF_EXECS[0]).__repr__()

        self.assertIn('Execution ', s)
        self.assertIn("'context': None", s)
        self.assertIn("'state': 'IDLE'", s)


TASK_EXECS = [
    {
        'workflow_execution_id': '1',
        'workflow_name': 'my_wb.my_wf',
        'name': 'my_task1',
        'spec': None,
        'action_spec': None,
        'state': 'IDLE',
        'tags': ['deployment'],
        'in_context': None,
        'runtime_context': None,
        'created_at': None,
        'updated_at': None
    },
    {
        'workflow_execution_id': '1',
        'workflow_name': 'my_wb.my_wf',
        'name': 'my_task2',
        'spec': None,
        'action_spec': None,
        'state': 'IDLE',
        'tags': ['deployment'],
        'in_context': {'image_id': '123123'},
        'runtime_context': None,
        'created_at': None,
        'updated_at': None
    },
]


class TaskExecutionTest(SQLAlchemyTest):
    def test_create_and_get_and_load_task_execution(self):
        wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

        values = copy.deepcopy(TASK_EXECS[0])
        values.update({'workflow_execution_id': wf_ex.id})

        created = db_api.create_task_execution(values)

        fetched = db_api.get_task_execution(created.id)

        self.assertEqual(created, fetched)

        self.assertNotIsInstance(fetched.workflow_execution, list)

        fetched = db_api.load_task_execution(created.id)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_task_execution("not-existing-id"))

    def test_action_executions(self):
        # Store one task with two invocations.
        with db_api.transaction():
            wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

            values = copy.deepcopy(TASK_EXECS[0])
            values.update({'workflow_execution_id': wf_ex.id})

            task = db_api.create_task_execution(values)

            self.assertEqual(0, len(task.action_executions))
            self.assertEqual(0, len(task.workflow_executions))

            a_ex1 = db_models.ActionExecution()
            a_ex2 = db_models.ActionExecution()

            task.action_executions.append(a_ex1)
            task.action_executions.append(a_ex2)

            self.assertEqual(2, len(task.action_executions))
            self.assertEqual(0, len(task.workflow_executions))

        # Make sure associated objects were saved.
        with db_api.transaction():
            task = db_api.get_task_execution(task.id)

            self.assertEqual(2, len(task.action_executions))

            self.assertNotIsInstance(
                task.action_executions[0].task_execution,
                list
            )

        # Remove associated objects from collection.
        with db_api.transaction():
            task = db_api.get_task_execution(task.id)

            del task.action_executions[:]

        # Make sure associated objects were deleted.
        with db_api.transaction():
            task = db_api.get_task_execution(task.id)

            self.assertEqual(0, len(task.action_executions))

    def test_update_task_execution(self):
        wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

        values = copy.deepcopy(TASK_EXECS[0])
        values.update({'workflow_execution_id': wf_ex.id})

        created = db_api.create_task_execution(values)

        self.assertIsNone(created.updated_at)

        updated = db_api.update_task_execution(
            created.id,
            {'workflow_name': 'new_wf'}
        )

        self.assertEqual('new_wf', updated.workflow_name)

        fetched = db_api.get_task_execution(created.id)

        self.assertEqual(updated, fetched)
        self.assertIsNotNone(fetched.updated_at)

    def test_create_or_update_task_execution(self):
        id = 'not-existing-id'

        self.assertIsNone(db_api.load_task_execution(id))

        wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

        values = copy.deepcopy(TASK_EXECS[0])
        values.update({'workflow_execution_id': wf_ex.id})

        created = db_api.create_or_update_task_execution(id, values)

        self.assertIsNotNone(created)
        self.assertIsNotNone(created.id)

        updated = db_api.create_or_update_task_execution(
            created.id,
            {'state': 'RUNNING'}
        )

        self.assertEqual('RUNNING', updated.state)
        self.assertEqual(
            'RUNNING',
            db_api.load_task_execution(updated.id).state
        )

        fetched = db_api.get_task_execution(created.id)

        self.assertEqual(updated, fetched)

    def test_get_task_executions(self):
        wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

        values = copy.deepcopy(TASK_EXECS[0])
        values.update({'workflow_execution_id': wf_ex.id})

        created0 = db_api.create_task_execution(values)

        values = copy.deepcopy(TASK_EXECS[1])
        values.update({'workflow_execution_id': wf_ex.id})

        created1 = db_api.create_task_execution(values)

        fetched = db_api.get_task_executions(
            workflow_name=TASK_EXECS[0]['workflow_name']
        )

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_delete_task_execution(self):
        wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

        values = copy.deepcopy(TASK_EXECS[0])
        values.update({'workflow_execution_id': wf_ex.id})

        created = db_api.create_task_execution(values)

        fetched = db_api.get_task_execution(created.id)

        self.assertEqual(created, fetched)

        db_api.delete_task_execution(created.id)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_task_execution,
            created.id
        )

    def test_get_incomplete_task_executions(self):
        wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

        values = copy.deepcopy(TASK_EXECS[0])
        values.update({'workflow_execution_id': wf_ex.id})
        values['state'] = 'RUNNING'

        task_ex1 = db_api.create_task_execution(values)

        task_execs = db_api.get_incomplete_task_executions(
            workflow_execution_id=wf_ex.id
        )

        self.assertEqual(1, len(task_execs))
        self.assertEqual(task_ex1, task_execs[0])
        self.assertEqual(
            1,
            db_api.get_incomplete_task_executions_count(
                workflow_execution_id=wf_ex.id
            )
        )

        # Add one more task.

        values = copy.deepcopy(TASK_EXECS[1])
        values.update({'workflow_execution_id': wf_ex.id})
        values['state'] = 'SUCCESS'

        db_api.create_task_execution(values)

        # It should be still one incompleted task.

        task_execs = db_api.get_incomplete_task_executions(
            workflow_execution_id=wf_ex.id
        )

        self.assertEqual(1, len(task_execs))
        self.assertEqual(task_ex1, task_execs[0])
        self.assertEqual(
            1,
            db_api.get_incomplete_task_executions_count(
                workflow_execution_id=wf_ex.id
            )
        )

    def test_task_execution_repr(self):
        wf_ex = db_api.create_workflow_execution(WF_EXECS[0])

        values = copy.deepcopy(TASK_EXECS[0])
        values.update({'workflow_execution_id': wf_ex.id})

        s = db_api.create_task_execution(values).__repr__()

        self.assertIn('TaskExecution ', s)
        self.assertIn("'state': 'IDLE'", s)
        self.assertIn("'name': 'my_task1'", s)


CRON_TRIGGERS = [
    {
        'name': 'trigger1',
        'pattern': '* * * * *',
        'workflow_name': 'my_wf',
        'workflow_id': None,
        'workflow_input': {},
        'next_execution_time':
        datetime.datetime.now() + datetime.timedelta(days=1),
        'remaining_executions': 42,
        'scope': 'private',
        'project_id': '<default-project>'
    },
    {
        'name': 'trigger2',
        'pattern': '* * * * *',
        'workflow_name': 'my_wf',
        'workflow_id': None,
        'workflow_input': {'param': 'val'},
        'next_execution_time':
        datetime.datetime.now() + datetime.timedelta(days=1),
        'remaining_executions': 42,
        'scope': 'private',
        'project_id': '<default-project>'
    },
]


class CronTriggerTest(SQLAlchemyTest):
    def setUp(self):
        super(CronTriggerTest, self).setUp()

        self.wf = db_api.create_workflow_definition({'name': 'my_wf'})

        for ct in CRON_TRIGGERS:
            ct['workflow_id'] = self.wf.id

    def test_create_and_get_and_load_cron_trigger(self):
        created = db_api.create_cron_trigger(CRON_TRIGGERS[0])

        fetched = db_api.get_cron_trigger(created.name)

        self.assertEqual(created, fetched)

        fetched = db_api.load_cron_trigger(created.name)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_cron_trigger("not-existing-trigger"))

    def test_create_cron_trigger_duplicate_without_auth(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')
        db_api.create_cron_trigger(CRON_TRIGGERS[0])

        self.assertRaises(
            exc.DBDuplicateEntryError,
            db_api.create_cron_trigger,
            CRON_TRIGGERS[0]
        )

    def test_update_cron_trigger(self):
        created = db_api.create_cron_trigger(CRON_TRIGGERS[0])

        self.assertIsNone(created.updated_at)

        updated, updated_count = db_api.update_cron_trigger(
            created.name,
            {'pattern': '*/1 * * * *'}
        )

        self.assertEqual('*/1 * * * *', updated.pattern)
        self.assertEqual(1, updated_count)

        fetched = db_api.get_cron_trigger(created.name)

        self.assertEqual(updated, fetched)
        self.assertIsNotNone(fetched.updated_at)

        # Test update_cron_trigger and query_filter with results
        updated, updated_count = db_api.update_cron_trigger(
            created.name,
            {'pattern': '*/1 * * * *'},
            query_filter={'name': created.name}
        )

        self.assertEqual(updated, fetched)
        self.assertEqual(1, updated_count)

        # Test update_cron_trigger and query_filter without results
        updated, updated_count = db_api.update_cron_trigger(
            created.name,
            {'pattern': '*/1 * * * *'},
            query_filter={'name': 'not-existing-id'}
        )

        self.assertEqual(updated, updated)
        self.assertEqual(0, updated_count)

    def test_create_or_update_cron_trigger(self):
        name = 'not-existing-id'

        self.assertIsNone(db_api.load_cron_trigger(name))

        created = db_api.create_or_update_cron_trigger(name, CRON_TRIGGERS[0])

        self.assertIsNotNone(created)
        self.assertIsNotNone(created.name)

        updated = db_api.create_or_update_cron_trigger(
            created.name,
            {'pattern': '*/1 * * * *'}
        )

        self.assertEqual('*/1 * * * *', updated.pattern)

        fetched = db_api.get_cron_trigger(created.name)

        self.assertEqual(updated, fetched)

    def test_get_cron_triggers(self):
        created0 = db_api.create_cron_trigger(CRON_TRIGGERS[0])
        created1 = db_api.create_cron_trigger(CRON_TRIGGERS[1])

        fetched = db_api.get_cron_triggers(pattern='* * * * *')

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_get_cron_triggers_other_tenant(self):
        created0 = db_api.create_cron_trigger(CRON_TRIGGERS[0])

        # Switch to another tenant.
        auth_context.set_ctx(user_context)

        fetched = db_api.get_cron_triggers(
            insecure=True,
            pattern='* * * * *',
            project_id=security.DEFAULT_PROJECT_ID
        )

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_delete_cron_trigger(self):
        created = db_api.create_cron_trigger(CRON_TRIGGERS[0])

        fetched = db_api.get_cron_trigger(created.name)

        self.assertEqual(created, fetched)

        rowcount = db_api.delete_cron_trigger(created.name)

        self.assertEqual(1, rowcount)
        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_cron_trigger,
            created.name
        )

    def test_cron_trigger_repr(self):
        s = db_api.create_cron_trigger(CRON_TRIGGERS[0]).__repr__()

        self.assertIn('CronTrigger ', s)
        self.assertIn("'pattern': '* * * * *'", s)
        self.assertIn("'name': 'trigger1'", s)


ENVIRONMENTS = [
    {
        'name': 'env1',
        'description': 'Test Environment #1',
        'scope': 'private',
        'variables': {
            'server': 'localhost',
            'database': 'test',
            'timeout': 600,
            'verbose': True
        }
    },
    {
        'name': 'env2',
        'description': 'Test Environment #2',
        'scope': 'public',
        'variables': {
            'server': '127.0.0.1',
            'database': 'temp',
            'timeout': 300,
            'verbose': False
        }
    }
]


class EnvironmentTest(SQLAlchemyTest):
    def setUp(self):
        super(EnvironmentTest, self).setUp()

        db_api.delete_environments()

    def test_create_and_get_and_load_environment(self):
        created = db_api.create_environment(ENVIRONMENTS[0])

        fetched = db_api.get_environment(created.name)

        self.assertEqual(created, fetched)

        fetched = db_api.load_environment(created.name)

        self.assertEqual(created, fetched)

        self.assertIsNone(db_api.load_environment("not-existing-id"))

    def test_create_environment_duplicate_without_auth(self):
        cfg.CONF.set_default('auth_enable', False, group='pecan')
        db_api.create_environment(ENVIRONMENTS[0])

        self.assertRaises(
            exc.DBDuplicateEntryError,
            db_api.create_environment,
            ENVIRONMENTS[0]
        )

    def test_update_environment(self):
        created = db_api.create_environment(ENVIRONMENTS[0])

        self.assertIsNone(created.updated_at)

        updated = db_api.update_environment(
            created.name,
            {'description': 'my new desc'}
        )

        self.assertEqual('my new desc', updated.description)

        fetched = db_api.get_environment(created.name)

        self.assertEqual(updated, fetched)
        self.assertIsNotNone(fetched.updated_at)

    def test_create_or_update_environment(self):
        name = 'not-existing-id'

        self.assertIsNone(db_api.load_environment(name))

        created = db_api.create_or_update_environment(name, ENVIRONMENTS[0])

        self.assertIsNotNone(created)
        self.assertIsNotNone(created.name)

        updated = db_api.create_or_update_environment(
            created.name,
            {'description': 'my new desc'}
        )

        self.assertEqual('my new desc', updated.description)
        self.assertEqual(
            'my new desc',
            db_api.load_environment(updated.name).description
        )

        fetched = db_api.get_environment(created.name)

        self.assertEqual(updated, fetched)

    def test_get_environments(self):
        created0 = db_api.create_environment(ENVIRONMENTS[0])
        created1 = db_api.create_environment(ENVIRONMENTS[1])

        fetched = db_api.get_environments()

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_delete_environment(self):
        created = db_api.create_environment(ENVIRONMENTS[0])

        fetched = db_api.get_environment(created.name)

        self.assertEqual(created, fetched)

        db_api.delete_environment(created.name)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_environment,
            created.name
        )

    def test_environment_repr(self):
        s = db_api.create_environment(ENVIRONMENTS[0]).__repr__()

        self.assertIn('Environment ', s)
        self.assertIn("'description': 'Test Environment #1'", s)
        self.assertIn("'name': 'env1'", s)


class TXTest(SQLAlchemyTest):
    def test_rollback(self):
        db_api.start_tx()

        try:
            created = db_api.create_workbook(WORKBOOKS[0])
            fetched = db_api.get_workbook(created.name)

            self.assertEqual(created, fetched)
            self.assertTrue(self.is_db_session_open())

            db_api.rollback_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())
        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workbook,
            created['id']
        )
        self.assertFalse(self.is_db_session_open())

    def test_commit(self):
        db_api.start_tx()

        try:
            created = db_api.create_workbook(WORKBOOKS[0])
            fetched = db_api.get_workbook(created.name)

            self.assertEqual(created, fetched)
            self.assertTrue(self.is_db_session_open())

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())

        fetched = db_api.get_workbook(created.name)

        self.assertEqual(created, fetched)
        self.assertFalse(self.is_db_session_open())

    def test_commit_transaction(self):
        with db_api.transaction():
            created = db_api.create_workbook(WORKBOOKS[0])
            fetched = db_api.get_workbook(created.name)

            self.assertEqual(created, fetched)
            self.assertTrue(self.is_db_session_open())

        self.assertFalse(self.is_db_session_open())

        fetched = db_api.get_workbook(created.name)

        self.assertEqual(created, fetched)
        self.assertFalse(self.is_db_session_open())

    def test_rollback_multiple_objects(self):
        db_api.start_tx()

        try:
            created = db_api.create_workflow_execution(WF_EXECS[0])
            fetched = db_api.get_workflow_execution(created['id'])

            self.assertEqual(created, fetched)

            created_wb = db_api.create_workbook(WORKBOOKS[0])
            fetched_wb = db_api.get_workbook(created_wb.name)

            self.assertEqual(created_wb, fetched_wb)
            self.assertTrue(self.is_db_session_open())

            db_api.rollback_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())
        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workflow_execution,
            created.id
        )
        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workbook,
            created_wb.name
        )

        self.assertFalse(self.is_db_session_open())

    def test_rollback_transaction(self):
        try:
            with db_api.transaction():
                created = db_api.create_workbook(WORKBOOKS[0])
                fetched = db_api.get_workbook(created.name)

                self.assertEqual(created, fetched)
                self.assertTrue(self.is_db_session_open())

                db_api.create_workbook(WORKBOOKS[0])

        except exc.DBDuplicateEntryError:
            pass

        self.assertFalse(self.is_db_session_open())
        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workbook,
            created.name
        )

    def test_commit_multiple_objects(self):
        db_api.start_tx()

        try:
            created = db_api.create_workflow_execution(WF_EXECS[0])
            fetched = db_api.get_workflow_execution(created.id)

            self.assertEqual(created, fetched)

            created_wb = db_api.create_workbook(WORKBOOKS[0])
            fetched_wb = db_api.get_workbook(created_wb.name)

            self.assertEqual(created_wb, fetched_wb)
            self.assertTrue(self.is_db_session_open())

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())

        fetched = db_api.get_workflow_execution(created.id)

        self.assertEqual(created, fetched)

        fetched_wb = db_api.get_workbook(created_wb.name)

        self.assertEqual(created_wb, fetched_wb)
        self.assertFalse(self.is_db_session_open())


RESOURCE_MEMBERS = [
    {
        'resource_id': '123e4567-e89b-12d3-a456-426655440000',
        'resource_type': 'workflow',
        'project_id': security.get_project_id(),
        'member_id': user_context.project_id,
        'status': 'pending',
    },
    {
        'resource_id': '123e4567-e89b-12d3-a456-426655440000',
        'resource_type': 'workflow',
        'project_id': security.get_project_id(),
        'member_id': '111',
        'status': 'pending',
    },
]


class ResourceMemberTest(SQLAlchemyTest):
    def test_create_and_get_resource_member(self):
        created_1 = db_api.create_resource_member(RESOURCE_MEMBERS[0])
        created_2 = db_api.create_resource_member(RESOURCE_MEMBERS[1])

        fetched = db_api.get_resource_member(
            '123e4567-e89b-12d3-a456-426655440000',
            'workflow',
            user_context.project_id
        )

        self.assertEqual(created_1, fetched)

        # Switch to another tenant.
        auth_context.set_ctx(user_context)

        fetched = db_api.get_resource_member(
            '123e4567-e89b-12d3-a456-426655440000',
            'workflow',
            user_context.project_id
        )

        self.assertEqual(created_1, fetched)

        # Tenant A can not see membership of resource shared to Tenant B.
        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_resource_member,
            '123e4567-e89b-12d3-a456-426655440000',
            'workflow',
            created_2.member_id
        )

    def test_create_resource_member_duplicate(self):
        db_api.create_resource_member(RESOURCE_MEMBERS[0])

        self.assertRaises(
            exc.DBDuplicateEntryError,
            db_api.create_resource_member,
            RESOURCE_MEMBERS[0]
        )

    def test_get_resource_members_by_owner(self):
        for res_member in RESOURCE_MEMBERS:
            db_api.create_resource_member(res_member)

        fetched = db_api.get_resource_members(
            '123e4567-e89b-12d3-a456-426655440000',
            'workflow',
        )

        self.assertTrue(2, len(fetched))

    def test_get_resource_members_not_owner(self):
        created = db_api.create_resource_member(RESOURCE_MEMBERS[0])
        db_api.create_resource_member(RESOURCE_MEMBERS[1])

        # Switch to another tenant.
        auth_context.set_ctx(user_context)

        fetched = db_api.get_resource_members(
            created.resource_id,
            'workflow',
        )

        self.assertTrue(1, len(fetched))
        self.assertEqual(created, fetched[0])

    def test_update_resource_member_by_member(self):
        created = db_api.create_resource_member(RESOURCE_MEMBERS[0])

        # Switch to another tenant.
        auth_context.set_ctx(user_context)

        updated = db_api.update_resource_member(
            created.resource_id,
            'workflow',
            user_context.project_id,
            {'status': 'accepted'}
        )

        self.assertEqual(created.id, updated.id)
        self.assertEqual('accepted', updated.status)

    def test_update_resource_member_by_owner(self):
        created = db_api.create_resource_member(RESOURCE_MEMBERS[0])

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.update_resource_member,
            created.resource_id,
            'workflow',
            user_context.project_id,
            {'status': 'accepted'}
        )

    def test_delete_resource_member(self):
        created = db_api.create_resource_member(RESOURCE_MEMBERS[0])

        db_api.delete_resource_member(
            created.resource_id,
            'workflow',
            user_context.project_id,
        )

        fetched = db_api.get_resource_members(
            created.resource_id,
            'workflow',
        )

        self.assertEqual(0, len(fetched))

    def test_delete_resource_member_not_owner(self):
        created = db_api.create_resource_member(RESOURCE_MEMBERS[0])

        # Switch to another tenant.
        auth_context.set_ctx(user_context)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.delete_resource_member,
            created.resource_id,
            'workflow',
            user_context.project_id,
        )

    def test_delete_resource_member_already_deleted(self):
        created = db_api.create_resource_member(RESOURCE_MEMBERS[0])

        db_api.delete_resource_member(
            created.resource_id,
            'workflow',
            user_context.project_id,
        )

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.delete_resource_member,
            created.resource_id,
            'workflow',
            user_context.project_id,
        )

    def test_delete_nonexistent_resource_member(self):
        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.delete_resource_member,
            'nonexitent_resource',
            'workflow',
            'nonexitent_member',
        )


class WorkflowSharingTest(SQLAlchemyTest):
    def test_get_shared_workflow(self):
        wf = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        # Switch to another tenant.
        auth_context.set_ctx(user_context)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workflow_definition,
            wf.id
        )

        # Switch to original tenant, share workflow to another tenant.
        auth_context.set_ctx(test_base.get_context())

        workflow_sharing = {
            'resource_id': wf.id,
            'resource_type': 'workflow',
            'project_id': security.get_project_id(),
            'member_id': user_context.project_id,
            'status': 'pending',
        }

        db_api.create_resource_member(workflow_sharing)

        # Switch to another tenant, accept the sharing, get workflows.
        auth_context.set_ctx(user_context)

        db_api.update_resource_member(
            wf.id,
            'workflow',
            user_context.project_id,
            {'status': 'accepted'}
        )

        fetched = db_api.get_workflow_definition(wf.id)

        self.assertEqual(wf, fetched)

    def test_owner_delete_shared_workflow(self):
        wf = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        workflow_sharing = {
            'resource_id': wf.id,
            'resource_type': 'workflow',
            'project_id': security.get_project_id(),
            'member_id': user_context.project_id,
            'status': 'pending',
        }

        db_api.create_resource_member(workflow_sharing)

        # Switch to another tenant, accept the sharing.
        auth_context.set_ctx(user_context)

        db_api.update_resource_member(
            wf.id,
            'workflow',
            user_context.project_id,
            {'status': 'accepted'}
        )

        fetched = db_api.get_workflow_definition(wf.id)

        self.assertEqual(wf, fetched)

        # Switch to original tenant, delete the workflow.
        auth_context.set_ctx(test_base.get_context())

        db_api.delete_workflow_definition(wf.id)

        # Switch to another tenant, can not see that workflow.
        auth_context.set_ctx(user_context)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_workflow_definition,
            wf.id
        )

    def test_owner_delete_shared_workflow_has_crontrigger(self):
        wf = db_api.create_workflow_definition(WF_DEFINITIONS[1])

        workflow_sharing = {
            'resource_id': wf.id,
            'resource_type': 'workflow',
            'project_id': security.get_project_id(),
            'member_id': user_context.project_id,
            'status': 'pending',
        }

        db_api.create_resource_member(workflow_sharing)

        # Switch to another tenant, accept the sharing.
        auth_context.set_ctx(user_context)

        db_api.update_resource_member(
            wf.id,
            'workflow',
            user_context.project_id,
            {'status': 'accepted'}
        )

        # Create cron trigger using the shared workflow.
        CRON_TRIGGERS[0]['workflow_id'] = wf.id
        db_api.create_cron_trigger(CRON_TRIGGERS[0])

        # Switch to original tenant, try to delete the workflow.
        auth_context.set_ctx(test_base.get_context())

        self.assertRaises(
            exc.DBError,
            db_api.delete_workflow_definition,
            wf.id
        )


EVENT_TRIGGERS = [
    {
        'name': 'trigger1',
        'workflow_id': '',
        'workflow_input': {},
        'workflow_params': {},
        'exchange': 'openstack',
        'topic': 'notification',
        'event': 'compute.create_instance',
    },
    {
        'name': 'trigger2',
        'workflow_id': '',
        'workflow_input': {},
        'workflow_params': {},
        'exchange': 'openstack',
        'topic': 'notification',
        'event': 'compute.delete_instance',
    },
]


class EventTriggerTest(SQLAlchemyTest):
    def setUp(self):
        super(EventTriggerTest, self).setUp()

        self.wf = db_api.create_workflow_definition({'name': 'my_wf'})

        for et in EVENT_TRIGGERS:
            et['workflow_id'] = self.wf.id

    def test_create_and_get_event_trigger(self):
        created = db_api.create_event_trigger(EVENT_TRIGGERS[0])

        fetched = db_api.get_event_trigger(created.id)

        self.assertEqual(created, fetched)

    def test_get_event_triggers_insecure(self):
        for t in EVENT_TRIGGERS:
            db_api.create_event_trigger(t)

        fetched = db_api.get_event_triggers()

        self.assertEqual(2, len(fetched))

    def test_get_event_triggers_not_insecure(self):
        db_api.create_event_trigger(EVENT_TRIGGERS[0])

        # Switch to another tenant.
        auth_context.set_ctx(user_context)

        db_api.create_event_trigger(EVENT_TRIGGERS[1])
        fetched = db_api.get_event_triggers()

        self.assertEqual(1, len(fetched))

        fetched = db_api.get_event_triggers(insecure=True)

        self.assertEqual(2, len(fetched))

    def test_update_event_trigger(self):
        created = db_api.create_event_trigger(EVENT_TRIGGERS[0])

        # Need a new existing workflow for updating event trigger because of
        # foreign constraint.
        new_wf = db_api.create_workflow_definition({'name': 'my_wf1'})

        db_api.update_event_trigger(
            created.id,
            {'workflow_id': new_wf.id}
        )

        updated = db_api.get_event_trigger(created.id)

        self.assertEqual(new_wf.id, updated.workflow_id)

    def test_delete_event_triggers(self):
        created = db_api.create_event_trigger(EVENT_TRIGGERS[0])

        db_api.delete_event_trigger(created.id)

        self.assertRaises(
            exc.DBEntityNotFoundError,
            db_api.get_event_trigger,
            created.id
        )


class LockTest(SQLAlchemyTest):
    def test_create_lock(self):
        # This test just ensures that DB model is OK.
        # It doesn't test the real intention of this model though.
        db_api.create_named_lock('lock1')

        locks = db_api.get_named_locks()

        self.assertEqual(1, len(locks))

        self.assertEqual('lock1', locks[0].name)

        db_api.delete_named_lock('invalid_lock_id')

        locks = db_api.get_named_locks()

        self.assertEqual(1, len(locks))

        db_api.delete_named_lock(locks[0].id)

        locks = db_api.get_named_locks()

        self.assertEqual(0, len(locks))

    def test_with_named_lock(self):
        name = 'lock1'

        with db_api.named_lock(name):
            # Make sure that within 'with' section the lock record exists.
            self.assertEqual(1, len(db_api.get_named_locks()))

        # Make sure that outside 'with' section the lock record does not exist.
        self.assertEqual(0, len(db_api.get_named_locks()))
