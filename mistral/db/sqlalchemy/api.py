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

from oslo.config import cfg
import sqlalchemy as sa

from mistral import context
from mistral.db.sqlalchemy import models as m
from mistral import exceptions as exc
from mistral.openstack.common.db import exception as db_exc
from mistral.openstack.common.db.sqlalchemy import session as db_session
from mistral.openstack.common import log as logging
from mistral import utils


LOG = logging.getLogger(__name__)

cfg.CONF.import_opt('connection',
                    'mistral.openstack.common.db.options',
                    group='database')

_DB_SESSION_THREAD_LOCAL_NAME = "db_sql_alchemy_session"

_facade = None


def get_facade():
    global _facade
    if not _facade:
        _facade = db_session.EngineFacade(
            cfg.CONF.database.connection, sqlite_fk=True, autocommit=False,
            **dict(cfg.CONF.database.iteritems()))
    return _facade


def get_engine():
    return get_facade().get_engine()


def get_session():
    return get_facade().get_session()


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


def setup_db():
    try:
        engine = get_engine()
        m.Trigger.metadata.create_all(engine)
    except sa.exc.OperationalError as e:
        LOG.exception("Database registration exception: %s", e)
        return False
    return True


def drop_db():
    global _facade
    try:
        engine = get_engine()
        m.Trigger.metadata.drop_all(engine)
        _facade = None
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

    ses = get_session()
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
            except Exception:
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

    _set_thread_local_session(get_session())


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
    """
    return session.query(model)


# Triggers.

@to_dict
@session_aware()
def trigger_create(values, session=None):
    trigger = m.Trigger()
    trigger.update(values.copy())

    try:
        trigger.save(session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Trigger: %s"
                                   % e.columns)

    return trigger


@to_dict
@session_aware()
def trigger_update(trigger_id, values, session=None):
    trigger = _trigger_get(trigger_id)
    if trigger is None:
        raise exc.NotFoundException("Trigger not found [trigger_id=%s]" %
                                    trigger_id)

    trigger.update(values.copy())

    return trigger


@session_aware()
def trigger_delete(trigger_id, session=None):
    trigger = _trigger_get(trigger_id)
    if not trigger:
        raise exc.NotFoundException("Trigger not found [trigger_id=%s]" %
                                    trigger_id)

    session.delete(trigger)


@to_dict
@session_aware()
def get_next_triggers(time, session=None):
    query = model_query(m.Trigger)
    query = query.filter(m.Trigger.next_execution_time < time)
    query = query.order_by(m.Trigger.next_execution_time)
    return query.all()


@session_aware()
def _trigger_get(trigger_id, session=None):
    query = model_query(m.Trigger)
    return query.filter_by(id=trigger_id).first()


@to_dict
def trigger_get(trigger_id):
    trigger = _trigger_get(trigger_id)
    if not trigger:
        raise exc.NotFoundException("Trigger not found [trigger_id=%s]" %
                                    trigger_id)
    return trigger


def _triggers_get_all(**kwargs):
    query = model_query(m.Trigger)
    return query.filter_by(**kwargs).all()


@to_dict
def triggers_get_all(**kwargs):
    return _triggers_get_all(**kwargs)


# Workbooks.

@to_dict
@session_aware()
def workbook_create(values, session=None):
    workbook = m.Workbook()
    workbook.update(values.copy())
    workbook['project_id'] = context.ctx().project_id

    try:
        workbook.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Workbook: %s"
                                   % e.columns)

    return workbook


@to_dict
@session_aware()
def workbook_update(workbook_name, values, session=None):
    workbook = _workbook_get(workbook_name)
    if not workbook:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % workbook_name)

    workbook.update(values.copy())
    workbook['project_id'] = context.ctx().project_id

    return workbook


@session_aware()
def workbook_delete(workbook_name, session=None):
    workbook = _workbook_get(workbook_name)
    if not workbook:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % workbook_name)

    session.delete(workbook)


@to_dict
def workbook_get(workbook_name):
    workbook = _workbook_get(workbook_name)
    if not workbook:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % workbook_name)
    return workbook


@to_dict
def workbooks_get_all(**kwargs):
    return _workbooks_get_all(**kwargs)


def _workbooks_get_all(**kwargs):
    query = model_query(m.Workbook)
    proj = query.filter_by(project_id=context.ctx().project_id,
                           **kwargs)
    public = query.filter_by(scope='public', **kwargs)
    return proj.union(public).all()


@session_aware()
def _workbook_get(workbook_name, session=None):
    query = model_query(m.Workbook)
    return query.filter_by(name=workbook_name,
                           project_id=context.ctx().project_id).first()


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
        raise exc.DBDuplicateEntry("Duplicate entry for Execution: %s"
                                   % e.columns)

    return execution


@to_dict
@session_aware()
def execution_update(execution_id, values, session=None):
    execution = _execution_get(execution_id)
    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % execution_id)

    execution.update(values.copy())

    return execution


@session_aware()
def execution_delete(execution_id, session=None):
    execution = _execution_get(execution_id)
    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % execution_id)

    session.delete(execution)


@to_dict
def execution_get(execution_id):
    execution = _execution_get(execution_id)
    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % execution_id)
    return execution


def ensure_execution_exists(execution_id):
    execution_get(execution_id)


@to_dict
def executions_get(**kwargs):
    return _executions_get(**kwargs)


def _executions_get(**kwargs):
    query = model_query(m.WorkflowExecution)
    return query.filter_by(**kwargs).all()


def _execution_get(execution_id):
    query = model_query(m.WorkflowExecution)
    return query.filter_by(id=execution_id).first()


# Workflow tasks.


@to_dict
@session_aware()
def task_create(execution_id, values, session=None):
    task = m.Task()
    task.update(values)
    task.update({'execution_id': execution_id})

    try:
        task.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Task: %s"
                                   % e.columns)

    return task


@to_dict
@session_aware()
def task_update(task_id, values, session=None):
    task = _task_get(task_id)
    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % task_id)

    task.update(values.copy())

    return task


@session_aware()
def task_delete(task_id, session=None):
    task = _task_get(task_id)
    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % task_id)

    session.delete(task)


@to_dict
def task_get(task_id):
    task = _task_get(task_id)
    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % task_id)

    return task


def _task_get(task_id):
    query = model_query(m.Task)
    return query.filter_by(id=task_id).first()


@to_dict
def tasks_get(**kwargs):
    return _tasks_get(**kwargs)


def _tasks_get(**kwargs):
    query = model_query(m.Task)
    return query.filter_by(**kwargs).all()
