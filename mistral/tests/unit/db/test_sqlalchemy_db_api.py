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

from mistral import context as auth_context
from mistral.db.sqlalchemy import api as db_api
from mistral import exceptions as exc
from mistral.openstack.common import timeutils
from mistral.tests import base as test_base


TRIGGERS = [
    {
        'id': '1',
        'name': 'test_trigger1',
        'workbook_name': 'my_workbook1',
        'pattern': '* *',
        'next_execution_time': timeutils.utcnow(),
        'updated_at': None
    },
    {
        'id': '2',
        'name': 'test_trigger2',
        'workbook_name': 'my_workbook2',
        'pattern': '* * *',
        'next_execution_time': timeutils.utcnow(),
        'updated_at': None
    }
]


class TriggerTest(test_base.DbTestCase):
    def test_trigger_create_and_get(self):
        created = db_api.trigger_create(TRIGGERS[0])
        self.assertIsInstance(created, dict)

        fetched = db_api.trigger_get(created['id'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

    def test_trigger_update(self):
        created = db_api.trigger_create(TRIGGERS[0])
        self.assertIsInstance(created, dict)

        updated = db_api.trigger_update(created['id'], {'pattern': '0 * *'})
        self.assertIsInstance(updated, dict)
        self.assertEqual('0 * *', updated['pattern'])

        fetched = db_api.trigger_get(created['id'])
        self.assertDictEqual(updated, fetched)

    def test_trigger_delete(self):
        created = db_api.trigger_create(TRIGGERS[0])
        db_api.trigger_delete(created['id'])

        self.assertRaises(exc.NotFoundException, db_api.trigger_get,
                          created['id'])

    def test_trigger_list(self):
        created0 = db_api.trigger_create(TRIGGERS[0])
        created1 = db_api.trigger_create(TRIGGERS[1])

        fetched = db_api.triggers_get_all()

        self.assertEqual(2, len(fetched))
        self.assertDictEqual(created0, fetched[0])
        self.assertDictEqual(created1, fetched[1])


WORKBOOKS = [
    {
        'id': '1',
        'name': 'my_workbook1',
        'description': 'my description',
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
        created = db_api.workbook_create(WORKBOOKS[0])
        self.assertIsInstance(created, dict)

        fetched = db_api.workbook_get(created['name'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

    def test_workbook_update(self):
        created = db_api.workbook_create(WORKBOOKS[0])
        self.assertIsInstance(created, dict)

        updated = db_api.workbook_update(created['name'],
                                         {'description': 'my new desc'})
        self.assertIsInstance(updated, dict)
        self.assertEqual('my new desc', updated['description'])

        fetched = db_api.workbook_get(created['name'])
        self.assertDictEqual(updated, fetched)

    def test_workbook_list(self):
        created0 = db_api.workbook_create(WORKBOOKS[0])
        created1 = db_api.workbook_create(WORKBOOKS[1])

        fetched = db_api.workbooks_get_all()

        self.assertEqual(2, len(fetched))
        self.assertDictEqual(created0, fetched[0])
        self.assertDictEqual(created1, fetched[1])

    def test_workbook_delete(self):
        created = db_api.workbook_create(WORKBOOKS[0])
        self.assertIsInstance(created, dict)

        fetched = db_api.workbook_get(created['name'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

        db_api.workbook_delete(created['name'])
        self.assertRaises(exc.NotFoundException,
                          db_api.workbook_get, created['name'])

    def test_workbook_private(self):
        # create a workbook(scope=private) as under one project
        # then make sure it's NOT visible for other projects.
        created1 = db_api.workbook_create(WORKBOOKS[1])

        fetched = db_api.workbooks_get_all()

        self.assertEqual(1, len(fetched))
        self.assertDictEqual(created1, fetched[0])

        # create a new user.
        ctx = auth_context.MistralContext(user_id='9-0-44-5',
                                          project_id='99-88-33',
                                          user_name='test-user',
                                          project_name='test-another',
                                          is_admin=False)
        auth_context.set_ctx(ctx)

        fetched = db_api.workbooks_get_all()
        self.assertEqual(0, len(fetched))

    def test_workbook_public(self):
        # create a workbook(scope=public) as under one project
        # then make sure it's visible for other projects.
        created0 = db_api.workbook_create(WORKBOOKS[0])

        fetched = db_api.workbooks_get_all()

        self.assertEqual(1, len(fetched))
        self.assertDictEqual(created0, fetched[0])

        # assert that the project_id stored is actually the context's
        # project_id not the one given.
        self.assertEqual(created0['project_id'], auth_context.ctx().project_id)
        self.assertNotEqual(WORKBOOKS[0]['project_id'],
                            auth_context.ctx().project_id)

        # create a new user.
        ctx = auth_context.MistralContext(user_id='9-0-44-5',
                                          project_id='99-88-33',
                                          user_name='test-user',
                                          project_name='test-another',
                                          is_admin=False)
        auth_context.set_ctx(ctx)

        fetched = db_api.workbooks_get_all()
        self.assertEqual(1, len(fetched))
        self.assertDictEqual(created0, fetched[0])
        self.assertEqual('public', created0['scope'])


EXECUTIONS = [
    {
        'id': '1',
        'workbook_name': 'my_workbook',
        'task': 'my_task1',
        'state': 'IDLE',
        'updated_at': None,
        'context': None
    },
    {
        'id': '2',
        'workbook_name': 'my_workbook',
        'task': 'my_task2',
        'state': 'RUNNING',
        'updated_at': None,
        'context': {'image_id': '123123'}
    }
]


class ExecutionTest(test_base.DbTestCase):
    def test_execution_create_and_get(self):
        created = db_api.execution_create(EXECUTIONS[0]['workbook_name'],
                                          EXECUTIONS[0])
        self.assertIsInstance(created, dict)

        fetched = db_api.execution_get(created['id'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

    def test_execution_update(self):
        created = db_api.execution_create(EXECUTIONS[0]['workbook_name'],
                                          EXECUTIONS[0])
        self.assertIsInstance(created, dict)

        updated = db_api.execution_update(created['id'],
                                          {'task': 'task10'})
        self.assertIsInstance(updated, dict)
        self.assertEqual('task10', updated['task'])

        fetched = db_api.execution_get(created['id'])
        self.assertDictEqual(updated, fetched)

    def test_execution_list(self):
        created0 = db_api.execution_create(EXECUTIONS[0]['workbook_name'],
                                           EXECUTIONS[0])
        created1 = db_api.execution_create(EXECUTIONS[1]['workbook_name'],
                                           EXECUTIONS[1])

        fetched = db_api.executions_get(
            workbook_name=EXECUTIONS[0]['workbook_name'])

        self.assertEqual(2, len(fetched))
        self.assertDictEqual(created0, fetched[0])
        self.assertDictEqual(created1, fetched[1])

    def test_execution_delete(self):
        created = db_api.execution_create(EXECUTIONS[0]['workbook_name'],
                                          EXECUTIONS[0])
        self.assertIsInstance(created, dict)

        fetched = db_api.execution_get(created['id'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

        db_api.execution_delete(created['id'])
        self.assertRaises(exc.NotFoundException,
                          db_api.execution_get,
                          created['id'])


TASKS = [
    {
        'id': '1',
        'workbook_name': 'my_workbook',
        'execution_id': '1',
        'name': 'my_task1',
        'description': 'my description',
        'requires': ['my_task2', 'my_task3'],
        'task_spec': None,
        'action_spec': None,
        'action': {'name': 'Nova:create-vm'},
        'state': 'IDLE',
        'tags': ['deployment'],
        'updated_at': None,
        'in_context': None,
        'parameters': None,
        'output': None,
        'task_runtime_context': None
    },
    {
        'id': '2',
        'workbook_name': 'my_workbook',
        'execution_id': '1',
        'name': 'my_task2',
        'description': 'my description',
        'requires': ['my_task4', 'my_task5'],
        'task_spec': None,
        'action_spec': None,
        'action': {'name': 'Cinder:create-volume'},
        'state': 'IDLE',
        'tags': ['deployment'],
        'updated_at': None,
        'in_context': {'image_id': '123123'},
        'parameters': {'image_id': '123123'},
        'output': {'vm_id': '343123'},
        'task_runtime_context': None
    },
]


class TaskTest(test_base.DbTestCase):
    def test_task_create_and_get(self):
        created = db_api.task_create(TASKS[0]['execution_id'],
                                     TASKS[0])
        self.assertIsInstance(created, dict)

        fetched = db_api.task_get(created['id'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

    def test_task_update(self):
        created = db_api.task_create(TASKS[0]['execution_id'],
                                     TASKS[0])
        self.assertIsInstance(created, dict)

        updated = db_api.task_update(created['id'],
                                     {'description': 'my new desc'})
        self.assertIsInstance(updated, dict)
        self.assertEqual('my new desc', updated['description'])

        fetched = db_api.task_get(created['id'])
        self.assertDictEqual(updated, fetched)

    def test_task_list(self):
        created0 = db_api.task_create(TASKS[0]['execution_id'],
                                      TASKS[0])
        created1 = db_api.task_create(TASKS[1]['execution_id'],
                                      TASKS[1])

        fetched = db_api.tasks_get(
            workbook_name=TASKS[0]['workbook_name'])

        self.assertEqual(2, len(fetched))
        self.assertDictEqual(created0, fetched[0])
        self.assertDictEqual(created1, fetched[1])

    def test_task_delete(self):
        created = db_api.task_create(TASKS[0]['execution_id'],
                                     TASKS[0])
        self.assertIsInstance(created, dict)

        fetched = db_api.task_get(created['id'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

        db_api.task_delete(created['id'])
        self.assertRaises(exc.NotFoundException, db_api.task_get,
                          created['id'])


class TXTest(test_base.DbTestCase):
    def test_rollback(self):
        db_api.start_tx()

        try:
            created = db_api.trigger_create(TRIGGERS[0])
            self.assertIsInstance(created, dict)

            fetched = db_api.trigger_get(created['id'])
            self.assertIsInstance(fetched, dict)
            self.assertDictEqual(created, fetched)

            self.assertTrue(self.is_db_session_open())

            db_api.rollback_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())

        self.assertRaises(exc.NotFoundException,
                          db_api.trigger_get, created['id'])

        self.assertFalse(self.is_db_session_open())

    def test_commit(self):
        db_api.start_tx()

        try:
            created = db_api.trigger_create(TRIGGERS[0])
            self.assertIsInstance(created, dict)

            fetched = db_api.trigger_get(created['id'])
            self.assertIsInstance(fetched, dict)
            self.assertDictEqual(created, fetched)

            self.assertTrue(self.is_db_session_open())

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())

        fetched = db_api.trigger_get(created['id'])
        self.assertIsInstance(fetched, dict)
        self.assertDictEqual(created, fetched)

        self.assertFalse(self.is_db_session_open())

    def test_rollback_multiple_objects(self):
        db_api.start_tx()

        try:
            created_trigger = db_api.trigger_create(TRIGGERS[0])
            self.assertIsInstance(created_trigger, dict)

            fetched_trigger = db_api.trigger_get(created_trigger['id'])
            self.assertIsInstance(fetched_trigger, dict)
            self.assertDictEqual(created_trigger, fetched_trigger)

            created_workbook = db_api.workbook_create(WORKBOOKS[0])
            self.assertIsInstance(created_workbook, dict)

            fetched_workbook = db_api.workbook_get(created_workbook['name'])
            self.assertIsInstance(fetched_workbook, dict)
            self.assertDictEqual(created_workbook, fetched_workbook)

            self.assertTrue(self.is_db_session_open())

            db_api.rollback_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())

        self.assertRaises(exc.NotFoundException,
                          db_api.trigger_get, created_trigger['id'])

        self.assertRaises(exc.NotFoundException, db_api.workbook_get,
                          created_workbook['name'])

        self.assertFalse(self.is_db_session_open())

    def test_commit_multiple_objects(self):
        db_api.start_tx()

        try:
            created_trigger = db_api.trigger_create(TRIGGERS[0])
            self.assertIsInstance(created_trigger, dict)

            fetched_trigger = db_api.trigger_get(created_trigger['id'])
            self.assertIsInstance(fetched_trigger, dict)
            self.assertDictEqual(created_trigger, fetched_trigger)

            created_workbook = db_api.workbook_create(WORKBOOKS[0])
            self.assertIsInstance(created_workbook, dict)

            fetched_workbook = db_api.workbook_get(created_workbook['name'])
            self.assertIsInstance(fetched_workbook, dict)
            self.assertDictEqual(created_workbook, fetched_workbook)

            self.assertTrue(self.is_db_session_open())

            db_api.commit_tx()
        finally:
            db_api.end_tx()

        self.assertFalse(self.is_db_session_open())

        fetched_trigger = db_api.trigger_get(created_trigger['id'])
        self.assertIsInstance(fetched_trigger, dict)
        self.assertDictEqual(created_trigger, fetched_trigger)

        fetched_workbook = db_api.workbook_get(created_workbook['name'])
        self.assertIsInstance(fetched_workbook, dict)
        self.assertDictEqual(created_workbook, fetched_workbook)

        self.assertFalse(self.is_db_session_open())
