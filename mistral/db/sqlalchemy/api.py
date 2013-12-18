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

from mistral import utils
from mistral import exceptions as exc
from mistral.db.sqlalchemy import models as m
from mistral.openstack.common.db.sqlalchemy import session as db_session
from mistral.openstack.common import log as logging
from mistral.openstack.common.db import exception as db_exc


LOG = logging.getLogger(__name__)

get_engine = db_session.get_engine
get_session = db_session.get_session

_DB_SESSION_THREAD_LOCAL_NAME = "db_sql_alchemy_session"


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


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


def _get_thread_local_session():
    return utils.get_thread_local(_DB_SESSION_THREAD_LOCAL_NAME)


def _get_or_create_thread_local_session():
    ses = _get_thread_local_session()

    if ses:
        return ses, False

    ses = get_session(autocommit=False)
    _set_thread_local_session(ses)

    return ses, True


def _set_thread_local_session(session):
    utils.set_thread_local(_DB_SESSION_THREAD_LOCAL_NAME, session)


def session_aware(param_name="session"):
    """Decorator for methods working within db session."""

    def _decorator(func):
        def _within_session(*args, **kw):
            # If 'created' flag is True it means that the transaction is
            # demarcated explicitly outside this module.
            ses, created = _get_or_create_thread_local_session()

            try:
                kw[param_name] = ses

                result = func(*args, **kw)

                if created:
                    ses.commit()

                return result
            except:
                if created:
                    ses.rollback()
                raise
            finally:
                if created:
                    _set_thread_local_session(None)
                    ses.close()

        _within_session.__doc__ = func.__doc__

        return _within_session

    return _decorator


# Transaction management.


def start_tx():
    """Opens new database session and starts new transaction assuming
        there wasn't any opened sessions within the same thread.
    """
    ses = _get_thread_local_session()
    if ses:
        raise exc.DataAccessException("Database transaction has already been"
                                      " started.")

    _set_thread_local_session(get_session(autocommit=False))


def commit_tx():
    """Commits previously started database transaction."""
    ses = _get_thread_local_session()
    if not ses:
        raise exc.DataAccessException("Nothing to commit. Database transaction"
                                      " has not been previously started.")

    ses.commit()


def rollback_tx():
    """Rolls back previously started database transaction."""
    ses = _get_thread_local_session()
    if not ses:
        raise exc.DataAccessException("Nothing to roll back. Database"
                                      " transaction has not been started.")

    ses.rollback()


def end_tx():
    """Ends current database transaction.
        It rolls back all uncommitted changes and closes database session.
    """
    ses = _get_thread_local_session()
    if not ses:
        raise exc.DataAccessException("Database transaction has not been"
                                      " started.")

    if ses.dirty:
        ses.rollback()

    ses.close()
    _set_thread_local_session(None)


@session_aware()
def model_query(model, session=None):
    """Query helper.

    :param model: base model to query
    :param context: context to query under
    :param project_only: if present and context is user-type, then restrict
            query to match the context's tenant_id.
    """
    return session.query(model)


# Events.

@to_dict
@session_aware()
def event_create(values, session=None):
    event = m.Event()
    event.update(values.copy())

    try:
        event.save(session)
    except db_exc.DBDuplicateEntry as e:
        LOG.exception("Database registration exception: %s", e)
        ##TODO(akuznetsov) create special exception for this case
        raise Exception

    return event


@to_dict
@session_aware()
def event_update(event_id, values, session=None):
    event = _event_get(event_id)
    if event is None:
        raise exc.DataAccessException("Event not found [event_id=%s]" %
                                      event_id)

    event.update(values.copy())

    return event


@to_dict
@session_aware()
def get_next_events(time, session=None):
    query = model_query(m.Event)
    query = query.filter(m.Event.next_execution_time < time)
    query = query.order_by(m.Event.next_execution_time)
    return query.all()


@session_aware()
def _event_get(event_id, session=None):
    query = model_query(m.Event)
    return query.filter_by(id=event_id).first()


@to_dict
def event_get(event_id):
    return _event_get(event_id)


def _events_get_all(**kwargs):
    query = model_query(m.Event)
    return query.filter_by(**kwargs).all()


@to_dict
def events_get_all(**kwargs):
    return _events_get_all(**kwargs)


# Workbooks.

@to_dict
@session_aware()
def workbook_create(values, session=None):
    workbook = m.Workbook()
    workbook.update(values.copy())

    try:
        workbook.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        LOG.exception("Database registration exception: %s", e)
        ##TODO(akuznetsov) create special exception for this case
        raise Exception

    return workbook


@to_dict
@session_aware()
def workbook_update(workbook_name, values, session=None):
    workbook = _workbook_get(workbook_name)
    if not workbook:
        raise exc.DataAccessException(
            "Workbook not found [workbook_name=%s]" % workbook_name)

    workbook.update(values.copy())

    return workbook


@session_aware()
def workbook_delete(workbook_name, session=None):
    workbook = _workbook_get(workbook_name)
    if not workbook:
        raise exc.DataAccessException(
            "Workbook not found [workbook_name=%s]" % workbook_name)

    session.delete(workbook)


@to_dict
def workbook_get(workbook_name):
    return _workbook_get(workbook_name)


@to_dict
def workbooks_get_all(**kwargs):
    return _workbooks_get_all(**kwargs)


def _workbooks_get_all(**kwargs):
    query = model_query(m.Workbook)
    return query.filter_by(**kwargs).all()


@session_aware()
def _workbook_get(workbook_name, session=None):
    query = model_query(m.Workbook)
    return query.filter_by(name=workbook_name).first()


# Workflow executions.

@to_dict
@session_aware()
def execution_create(workbook_name, values, session=None):
    execution = m.WorkflowExecution()
    execution.update(values.copy())
    execution.update({'workbook_name': workbook_name})

    try:
        execution.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        LOG.exception("Database registration exception: %s", e)
        ##TODO(akuznetsov) create special exception for this case
        raise Exception

    return execution


@to_dict
@session_aware()
def execution_update(workbook_name, execution_id, values, session=None):
    execution = _execution_get(workbook_name, execution_id)
    if not execution:
        raise exc.DataAccessException(
            "Execution not found [workbook_name=%s, execution_id=%s]" %
            (workbook_name, execution_id))
    execution.update(values.copy())

    return execution


@session_aware()
def execution_delete(workbook_name, execution_id, session=None):
    execution = _execution_get(workbook_name, execution_id)
    if not execution:
        raise exc.DataAccessException(
            "Execution not found [workbook_name=%s, execution_id=%s]" %
            (workbook_name, execution_id))

    session.delete(execution)


@to_dict
def execution_get(workbook_name, execution_id):
    return _execution_get(workbook_name, execution_id)


@to_dict
def executions_get_all(**kwargs):
    return _executions_get_all(**kwargs)


def _executions_get_all(**kwargs):
    query = model_query(m.WorkflowExecution)
    return query.filter_by(**kwargs).all()


def _execution_get(workbook_name, execution_id):
    query = model_query(m.WorkflowExecution)
    return query.filter_by(id=execution_id,
                           workbook_name=workbook_name).first()


# Workflow tasks.


@to_dict
@session_aware()
def task_create(workbook_name, execution_id, values, session=None):
    task = m.Task()
    task.update(values)
    task.update({
        'workbook_name': workbook_name,
        'execution_id': execution_id
    })

    try:
        task.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        LOG.exception("Database registration exception: %s", e)
        ##TODO(akuznetsov) create special exception for this case
        raise Exception

    return task


@to_dict
@session_aware()
def task_update(workbook_name, execution_id, task_id, values, session=None):
    task = _task_get(workbook_name, execution_id, task_id)
    if not task:
        raise exc.DataAccessException(
            "Task not found [workbook_name=%s, execution_id=%s, task_id=%s]" %
            (workbook_name, execution_id, task_id))

    task.update(values.copy())

    return task


@session_aware()
def task_delete(workbook_name, execution_id, task_id, session=None):
    task = _task_get(workbook_name, execution_id, task_id)
    if not task:
        raise exc.DataAccessException(
            "Task not found [workbook_name=%s, execution_id=%s, task_id=%s]" %
            (workbook_name, execution_id, task_id))

    session.delete(task)


@to_dict
def task_get(workbook_name, execution_id, task_id):
    return _task_get(workbook_name, execution_id, task_id)


def _task_get(workbook_name, execution_id, task_id):
    query = model_query(m.Task)
    return query.filter_by(id=task_id,
                           workbook_name=workbook_name,
                           execution_id=execution_id).first()


@to_dict
def tasks_get_all(**kwargs):
    return _tasks_get_all(**kwargs)


def _tasks_get_all(**kwargs):
    query = model_query(m.Task)
    return query.filter_by(**kwargs).all()
