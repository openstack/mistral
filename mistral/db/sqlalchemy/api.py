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

import sys
import sqlalchemy as sa

from mistral.db.sqlalchemy import models as m
from mistral.openstack.common.db.sqlalchemy import session as db_session
from mistral.openstack.common import log as logging
from mistral.openstack.common.db import exception as db_exc


LOG = logging.getLogger(__name__)

get_engine = db_session.get_engine
get_session = db_session.get_session


def to_dict(func):
    def decorator(*args, **kwargs):
        res = func(*args, **kwargs)

        if isinstance(res, list):
            return [item.to_dict() for item in res]

        if res:
            return res.to_dict()
        else:
            return None

    return decorator


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


def model_query(model, session=None):
    """Query helper.

    :param model: base model to query
    :param context: context to query under
    :param project_only: if present and context is user-type, then restrict
            query to match the context's tenant_id.
    """
    session = session or get_session()

    return session.query(model)


def setup_db():
    try:
        engine = db_session.get_engine(sqlite_fk=True)
        m.Event.metadata.create_all(engine)
    except sa.exc.OperationalError as e:
        LOG.exception("Database registration exception: %s", e)
        return False
    return True


def drop_db():
    try:
        engine = db_session.get_engine(sqlite_fk=True)
        m.Event.metadata.drop_all(engine)
    except Exception as e:
        LOG.exception("Database shutdown exception: %s", e)
        return False
    return True


def start_tx():
    # TODO(rakhmerov): implement
    raise NotImplemented


def commit_tx():
    # TODO(rakhmerov): implement
    raise NotImplemented


def rollback_tx():
    # TODO(rakhmerov): implement
    raise NotImplemented


def end_tx():
    # TODO(rakhmerov): implement
    raise NotImplemented


def event_create(values):
    values = values.copy()
    event = m.Event()
    event.update(values)

    session = get_session()
    with session.begin():
        try:
            event.save(session=session)
        except db_exc.DBDuplicateEntry as e:
            LOG.exception("Database registration exception: %s", e)
            ##TODO(akuznetsov) create special exception for this case
            raise Exception

    return event_get(event.id)


def event_update(event_id, values):
    values = values.copy()

    session = get_session()
    with session.begin():
        event = _event_get(event_id, session)
        if event is None:
            ##TODO(akuznetsov) create special exception for this case
            raise Exception
        event.update(values)

    return event


@to_dict
def get_next_events(time):
    query = model_query(m.Event, get_session())
    query = query.filter(m.Event.next_execution_time < time)
    query = query.order_by(m.Event.next_execution_time)
    return query.all()


def _event_get(event_id, session):
    query = model_query(m.Event, session)
    return query.filter_by(id=event_id).first()


@to_dict
def event_get(event_id):
    return _event_get(event_id, get_session())


@to_dict
def events_get_all(**kwargs):
    return _events_get_all(get_session(), **kwargs)


def _events_get_all(session, **kwargs):
    query = model_query(m.Event, session)
    return query.filter_by(**kwargs).all()


def workbook_create(values):
    values = values.copy()
    workbook = m.Workbook()
    workbook.update(values)

    session = get_session()
    with session.begin():
        try:
            workbook.save(session=session)
        except db_exc.DBDuplicateEntry as e:
            LOG.exception("Database registration exception: %s", e)
            ##TODO(akuznetsov) create special exception for this case
            raise Exception

    return workbook_get(workbook.name)


def workbook_update(workbook_name, values):
    values = values.copy()

    session = get_session()
    with session.begin():
        workbook = _workbook_get(workbook_name, session)
        if workbook is None:
            ##TODO(akuznetsov) create special exception for this case
            raise Exception
        workbook.update(values)

    return workbook


def workbook_delete(workbook_name):
    session = get_session()
    with session.begin():
        workbook = _workbook_get(workbook_name, session)
        if not workbook:
            raise Exception

        session.delete(workbook)


@to_dict
def workbook_get(workbook_name):
    return _workbook_get(workbook_name, get_session())


@to_dict
def workbooks_get_all(**kwargs):
    return _workbooks_get_all(get_session(), **kwargs)


def _workbooks_get_all(session, **kwargs):
    query = model_query(m.Workbook, session)
    return query.filter_by(**kwargs).all()


def _workbook_get(workbook_name, session):
    query = model_query(m.Workbook, session)
    return query.filter_by(name=workbook_name).first()


@to_dict
def execution_get(workbook_name, execution_id):
    return _execution_get(workbook_name, execution_id, get_session())


@to_dict
def executions_get_all(**kwargs):
    return _executions_get_all(get_session(), **kwargs)


def _executions_get_all(session, **kwargs):
    query = model_query(m.WorkflowExecution, session)
    return query.filter_by(**kwargs).all()


def _execution_get(workbook_name, execution_id, session):
    query = model_query(m.WorkflowExecution, session)
    return query.filter_by(id=execution_id,
                           workbook_name=workbook_name).first()


def execution_update(workbook_name, execution_id, values):
    values = values.copy()

    session = get_session()
    with session.begin():
        execution = _execution_get(workbook_name, execution_id, session)
        if execution is None:
            ##TODO(akuznetsov) create special exception for this case
            raise Exception
        execution.update(values)

    return execution


def execution_delete(workbook_name, execution_id):
    session = get_session()
    with session.begin():
        execution = _execution_get(workbook_name, execution_id, session)
        if not execution:
            raise Exception

        session.delete(execution)


def execution_create(workbook_name, values):
    execution = m.WorkflowExecution()
    execution.update(values.copy())
    execution.update({'workbook_name': workbook_name})

    session = get_session()
    with session.begin():
        try:
            execution.save(session=session)
        except db_exc.DBDuplicateEntry as e:
            LOG.exception("Database registration exception: %s", e)
            ##TODO(akuznetsov) create special exception for this case
            raise Exception

    return execution_get(workbook_name, execution.id)


@to_dict
def task_get(workbook_name, execution_id, task_id):
    return _task_get(workbook_name, execution_id, task_id, get_session())


def _task_get(workbook_name, execution_id, task_id, session):
    query = model_query(m.Task, session)
    return query.filter_by(id=task_id,
                           workbook_name=workbook_name,
                           execution_id=execution_id).first()


@to_dict
def tasks_get_all(**kwargs):
    return _tasks_get_all(get_session(), **kwargs)


def _tasks_get_all(session, **kwargs):
    query = model_query(m.Task, session)
    return query.filter_by(**kwargs).all()


def task_update(workbook_name, execution_id, task_id, values):
    values = values.copy()

    session = get_session()
    with session.begin():
        task = _task_get(workbook_name, execution_id, task_id, session)
        if task is None:
            ##TODO(akuznetsov) create special exception for this case
            raise Exception
        task.update(values)

    return task


def task_delete(workbook_name, execution_id, task_id):
    session = get_session()
    with session.begin():
        task = _task_get(workbook_name, execution_id, task_id, session)
        if not task:
            raise Exception

        session.delete(task)


def task_create(workbook_name, execution_id, values):
    values = values.copy()
    task = m.Task()
    task.update(values)
    task.update({
        'workbook_name': workbook_name,
        'execution_id': execution_id
    })

    session = get_session()
    with session.begin():
        try:
            task.save(session=session)
        except db_exc.DBDuplicateEntry as e:
            LOG.exception("Database registration exception: %s", e)
            ##TODO(akuznetsov) create special exception for this case
            raise Exception

    return task_get(workbook_name, execution_id, task.id)
