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

# TODO(rakhmerov): Add checks for timestamps.

import copy

from mistral import context as auth_context
from mistral.db.v2.sqlalchemy import api as db_api
from mistral import exceptions as exc
from mistral.tests import base as test_base


WORKBOOKS = [
    {
        'id': '1',
        'name': 'my_workbook1',
        'definition': 'empty',
        'tags': ['mc'],
        'scope': 'public',
        'updated_at': None,
        'project_id': '1233',
        'trust_id': '1234'
    },
    {
        'id': '2',
        'name': 'my_workbook2',
        'description': 'my description',
        'definition': 'empty',
        'tags': ['mc'],
        'scope': 'private',
        'updated_at': None,
        'project_id': '1233',
        'trust_id': '12345'
    },
]


class WorkbookTest(test_base.DbTestCase):
    def test_workbook_create_and_get(self):
        created = db_api.create_workbook(WORKBOOKS[0])

        fetched = db_api.get_workbook(created['name'])

        self.assertEqual(created, fetched)

    def test_workbook_update(self):
        created = db_api.create_workbook(WORKBOOKS[0])

        updated = db_api.update_workbook(
            created['name'],
            {'description': 'my new desc'}
        )

        self.assertEqual('my new desc', updated['description'])

        fetched = db_api.get_workbook(created['name'])

        self.assertEqual(updated, fetched)

    def test_workbook_list(self):
        created0 = db_api.create_workbook(WORKBOOKS[0])
        created1 = db_api.create_workbook(WORKBOOKS[1])

        fetched = db_api.get_workbooks()

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_workbook_delete(self):
        created = db_api.create_workbook(WORKBOOKS[0])

        fetched = db_api.get_workbook(created['name'])

        self.assertEqual(created, fetched)

        db_api.delete_workbook(created['name'])

        self.assertRaises(
            exc.NotFoundException,
            db_api.get_workbook,
            created['name']
        )

    def test_workbook_private(self):
        # Create a workbook(scope=private) as under one project
        # then make sure it's NOT visible for other projects.
        created1 = db_api.create_workbook(WORKBOOKS[1])

        fetched = db_api.get_workbooks()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created1, fetched[0])

        # Create a new user.
        ctx = auth_context.MistralContext(
            user_id='9-0-44-5',
            project_id='99-88-33',
            user_name='test-user',
            project_name='test-another',
            is_admin=False
        )

        auth_context.set_ctx(ctx)

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
        self.assertEqual(created0['project_id'], auth_context.ctx().project_id)
        self.assertNotEqual(WORKBOOKS[0]['project_id'],
                            auth_context.ctx().project_id)

        # Create a new user.
        ctx = auth_context.MistralContext(
            user_id='9-0-44-5',
            project_id='99-88-33',
            user_name='test-user',
            project_name='test-another',
            is_admin=False
        )

        auth_context.set_ctx(ctx)

        fetched = db_api.get_workbooks()

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual('public', created0['scope'])

    def test_workbook_repr(self):
        s = db_api.create_workbook(WORKBOOKS[0]).__repr__()

        self.assertIn('Workbook ', s)
        self.assertIn("'name': 'my_workbook1'", s)

EXECUTIONS = [
    {
        'id': '1',
        'wf_spec': {},
        'start_params': {'task': 'my_task1'},
        'state': 'IDLE',
        'created_at': None,
        'updated_at': None,
        'context': None
    },
    {
        'id': '2',
        'wf_spec': {},
        'start_params': {'task': 'my_task1'},
        'state': 'RUNNING',
        'created_at': None,
        'updated_at': None,
        'context': {'image_id': '123123'}
    }
]


class ExecutionTest(test_base.DbTestCase):
    def test_execution_create_and_get(self):
        created = db_api.create_execution(EXECUTIONS[0])

        fetched = db_api.get_execution(created['id'])

        self.assertEqual(created, fetched)

    def test_execution_update(self):
        created = db_api.create_execution(EXECUTIONS[0])

        updated = db_api.update_execution(created['id'],
                                          {'task': 'task10'})

        self.assertEqual('task10', updated['task'])

        fetched = db_api.get_execution(created['id'])

        self.assertEqual(updated, fetched)

    def test_execution_list(self):
        created0 = db_api.create_execution(EXECUTIONS[0])
        db_api.create_execution(EXECUTIONS[1])

        fetched = db_api.get_executions(
            state=EXECUTIONS[0]['state']
        )

        self.assertEqual(1, len(fetched))
        self.assertEqual(created0, fetched[0])

    def test_execution_delete(self):
        created = db_api.create_execution(EXECUTIONS[0])

        fetched = db_api.get_execution(created['id'])

        self.assertEqual(created, fetched)

        db_api.delete_execution(created['id'])

        self.assertRaises(
            exc.NotFoundException,
            db_api.get_execution,
            created['id']
        )

    def test_execution_repr(self):
        s = db_api.create_execution(EXECUTIONS[0]).__repr__()

        self.assertIn('Execution ', s)
        self.assertIn("'id': '1'", s)
        self.assertIn("'state': 'IDLE'", s)


TASKS = [
    {
        'id': '1',
        'execution_id': '1',
        'wf_name': 'my_wb.my_wf',
        'name': 'my_task1',
        'requires': ['my_task2', 'my_task3'],
        'spec': None,
        'action_spec': None,
        'state': 'IDLE',
        'tags': ['deployment'],
        'in_context': None,
        'parameters': None,
        'output': None,
        'runtime_context': None,
        'created_at': None,
        'updated_at': None
    },
    {
        'id': '2',
        'execution_id': '1',
        'wf_name': 'my_wb.my_wf',
        'name': 'my_task2',
        'requires': ['my_task4', 'my_task5'],
        'spec': None,
        'action_spec': None,
        'state': 'IDLE',
        'tags': ['deployment'],
        'in_context': {'image_id': '123123'},
        'parameters': {'image_id': '123123'},
        'output': {'vm_id': '343123'},
        'runtime_context': None,
        'created_at': None,
        'updated_at': None
    },
]


class TaskTest(test_base.DbTestCase):
    def test_task_create_and_get(self):
        ex = db_api.create_execution(EXECUTIONS[0])

        values = copy.copy(TASKS[0])
        values.update({'execution_id': ex.id})

        created = db_api.create_task(values)

        fetched = db_api.get_task(created['id'])

        self.assertEqual(created, fetched)

    def test_task_update(self):
        ex = db_api.create_execution(EXECUTIONS[0])

        values = copy.copy(TASKS[0])
        values.update({'execution_id': ex.id})

        created = db_api.create_task(values)

        updated = db_api.update_task(
            created['id'],
            {'description': 'my new desc'}
        )

        self.assertEqual('my new desc', updated['description'])

        fetched = db_api.get_task(created['id'])

        self.assertEqual(updated, fetched)

    def test_task_list(self):
        ex = db_api.create_execution(EXECUTIONS[0])

        values = copy.copy(TASKS[0])
        values.update({'execution_id': ex.id})

        created0 = db_api.create_task(values)

        values = copy.copy(TASKS[1])
        values.update({'execution_id': ex.id})

        created1 = db_api.create_task(values)

        fetched = db_api.get_tasks(wf_name=TASKS[0]['wf_name'])

        self.assertEqual(2, len(fetched))
        self.assertEqual(created0, fetched[0])
        self.assertEqual(created1, fetched[1])

    def test_task_delete(self):
        ex = db_api.create_execution(EXECUTIONS[0])

        values = copy.copy(TASKS[0])
        values.update({'execution_id': ex.id})

        created = db_api.create_task(values)

        fetched = db_api.get_task(created['id'])

        self.assertEqual(created, fetched)

        db_api.delete_task(created['id'])

        self.assertRaises(
            exc.NotFoundException,
            db_api.get_task,
            created['id']
        )

    def test_task_repr(self):
        ex = db_api.create_execution(EXECUTIONS[0])

        values = copy.copy(TASKS[0])
        values.update({'execution_id': ex.id})

        s = db_api.create_task(values).__repr__()

        self.assertIn('Task ', s)
        self.assertIn("'id': '1'", s)
        self.assertIn("'name': 'my_task1'", s)


class TXTest(test_base.DbTestCase):
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
            exc.NotFoundException,
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

    def test_rollback_multiple_objects(self):
        db_api.start_tx()

        try:
            created = db_api.create_execution(EXECUTIONS[0])
            fetched = db_api.get_execution(created['id'])

            self.assertEqual(created, fetched)

            created_workbook = db_api.create_workbook(WORKBOOKS[0])
            fetched_workbook = db_api.get_workbook(created_workbook['name'])

            self.assertEqual(created_workbook, fetched_workbook)
            self.assertTrue(self.is_db_session_open())

            db_api.rollback_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())
        self.assertRaises(
            exc.NotFoundException,
            db_api.get_execution,
            created['id']
        )
        self.assertRaises(
            exc.NotFoundException,
            db_api.get_workbook,
            created_workbook['name']
        )

        self.assertFalse(self.is_db_session_open())

    def test_commit_multiple_objects(self):
        db_api.start_tx()

        try:
            created = db_api.create_execution(EXECUTIONS[0])
            fetched = db_api.get_execution(created['id'])

            self.assertEqual(created, fetched)

            created_workbook = db_api.create_workbook(WORKBOOKS[0])
            fetched_workbook = db_api.get_workbook(created_workbook['name'])

            self.assertEqual(created_workbook, fetched_workbook)
            self.assertTrue(self.is_db_session_open())

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())

        fetched = db_api.get_execution(created['id'])

        self.assertEqual(created, fetched)

        fetched_workbook = db_api.get_workbook(created_workbook['name'])

        self.assertEqual(created_workbook, fetched_workbook)
        self.assertFalse(self.is_db_session_open())
