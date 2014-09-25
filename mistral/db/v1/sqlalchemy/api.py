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

import contextlib
import sys

from oslo.db import exception as db_exc
import sqlalchemy as sa

from mistral import context
from mistral.db.sqlalchemy import base as b
from mistral.db.v1.sqlalchemy import models
from mistral import exceptions as exc
from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def get_backend():
    """Consumed by openstack common code.

    The backend is this module itself.
    :return Name of db backend.
    """
    return sys.modules[__name__]


def setup_db():
    try:
        models.Workbook.metadata.create_all(b.get_engine())
    except sa.exc.OperationalError as e:
        raise exc.DBException("Failed to setup database: %s" % e)


def drop_db():
    global _facade

    try:
        models.Workbook.metadata.drop_all(b.get_engine())
        _facade = None
    except Exception as e:
        raise exc.DBException("Failed to drop database: %s" % e)


# Transaction management.

def start_tx():
    b.start_tx()


def commit_tx():
    b.commit_tx()


def rollback_tx():
    b.rollback_tx()


def end_tx():
    b.end_tx()


@contextlib.contextmanager
def transaction():
    try:
        start_tx()
        yield
        commit_tx()
    finally:
        end_tx()


def _delete_all(model, session=None, **kwargs):
    query = b.model_query(model)
    query.filter_by(**kwargs).delete()


# Triggers.

@b.session_aware()
def trigger_create(values, session=None):
    trigger = models.Trigger()
    trigger.update(values.copy())

    try:
        trigger.save(session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Trigger: %s"
                                   % e.columns)

    return trigger


@b.session_aware()
def trigger_update(trigger_id, values, session=None):
    trigger = _trigger_get(trigger_id)
    if trigger is None:
        raise exc.NotFoundException("Trigger not found [trigger_id=%s]" %
                                    trigger_id)

    trigger.update(values.copy())

    return trigger


@b.session_aware()
def trigger_delete(trigger_id, session=None):
    trigger = _trigger_get(trigger_id)
    if not trigger:
        raise exc.NotFoundException("Trigger not found [trigger_id=%s]" %
                                    trigger_id)

    session.delete(trigger)


@b.session_aware()
def get_next_triggers(time, session=None):
    query = b.model_query(models.Trigger)
    query = query.filter(models.Trigger.next_execution_time < time)
    query = query.order_by(models.Trigger.next_execution_time)
    return query.all()


@b.session_aware()
def _trigger_get(trigger_id, session=None):
    query = b.model_query(models.Trigger)
    return query.filter_by(id=trigger_id).first()


def trigger_get(trigger_id):
    trigger = _trigger_get(trigger_id)
    if not trigger:
        raise exc.NotFoundException("Trigger not found [trigger_id=%s]" %
                                    trigger_id)
    return trigger


def _triggers_get_all(**kwargs):
    query = b.model_query(models.Trigger)
    return query.filter_by(**kwargs).all()


def triggers_get_all(**kwargs):
    return _triggers_get_all(**kwargs)


@b.session_aware()
def triggers_delete(**kwargs):
    return _delete_all(models.Trigger, **kwargs)


# Workbooks.

@b.session_aware()
def workbook_create(values, session=None):
    workbook = models.Workbook()
    workbook.update(values.copy())
    workbook['project_id'] = context.ctx().project_id

    try:
        workbook.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Workbook: %s"
                                   % e.columns)

    return workbook


@b.session_aware()
def workbook_update(workbook_name, values, session=None):
    workbook = _workbook_get(workbook_name)

    if not workbook:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % workbook_name)

    workbook.update(values.copy())
    workbook['project_id'] = context.ctx().project_id

    return workbook


@b.session_aware()
def workbook_delete(workbook_name, session=None):
    workbook = _workbook_get(workbook_name)
    if not workbook:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % workbook_name)

    session.delete(workbook)


def workbook_get(workbook_name):
    workbook = _workbook_get(workbook_name)

    if not workbook:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % workbook_name)

    return workbook


def workbooks_get_all(**kwargs):
    return _workbooks_get_all(**kwargs)


def _workbooks_get_all(**kwargs):
    query = b.model_query(models.Workbook)
    proj = query.filter_by(project_id=context.ctx().project_id,
                           **kwargs)
    public = query.filter_by(scope='public', **kwargs)
    return proj.union(public).all()


@b.session_aware()
def _workbook_get(workbook_name, session=None):
    query = b.model_query(models.Workbook)
    if context.ctx().is_admin:
        return query.filter_by(name=workbook_name).first()
    else:
        return query.filter_by(name=workbook_name,
                               project_id=context.ctx().project_id).first()


@b.session_aware()
def workbooks_delete(**kwargs):
    return _delete_all(models.Workbook, **kwargs)


# Workflow executions.


@b.session_aware()
def execution_create(workbook_name, values, session=None):
    execution = models.WorkflowExecution()
    execution.update(values.copy())
    execution.update({'workbook_name': workbook_name})

    try:
        execution.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Execution: %s"
                                   % e.columns)

    return execution


@b.session_aware()
def execution_update(execution_id, values, session=None):
    execution = _execution_get(execution_id)
    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % execution_id)

    execution.update(values.copy())

    return execution


@b.session_aware()
def execution_delete(execution_id, session=None):
    execution = _execution_get(execution_id)
    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % execution_id)

    session.delete(execution)


@b.session_aware()
def executions_delete(**kwargs):
    return _delete_all(models.WorkflowExecution, **kwargs)


def execution_get(execution_id):
    execution = _execution_get(execution_id)

    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % execution_id)

    return execution


def ensure_execution_exists(execution_id):
    execution_get(execution_id)


def executions_get(**kwargs):
    return _executions_get(**kwargs)


def _executions_get(**kwargs):
    query = b.model_query(models.WorkflowExecution)
    return query.filter_by(**kwargs).all()


def _execution_get(execution_id):
    query = b.model_query(models.WorkflowExecution)

    return query.filter_by(id=execution_id).first()


# Workflow tasks.


@b.session_aware()
def task_create(execution_id, values, session=None):
    task = models.Task()
    task.update(values)
    task.update({'execution_id': execution_id})

    try:
        task.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Task: %s"
                                   % e.columns)

    return task


@b.session_aware()
def task_update(task_id, values, session=None):
    task = _task_get(task_id)
    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % task_id)

    task.update(values.copy())

    return task


@b.session_aware()
def task_delete(task_id, session=None):
    task = _task_get(task_id)
    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % task_id)

    session.delete(task)


@b.session_aware()
def tasks_delete(**kwargs):
    return _delete_all(models.Task, **kwargs)


def task_get(task_id):
    task = _task_get(task_id)
    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % task_id)

    return task


def _task_get(task_id):
    query = b.model_query(models.Task)
    return query.filter_by(id=task_id).first()


def tasks_get(**kwargs):
    return _tasks_get(**kwargs)


def _tasks_get(**kwargs):
    query = b.model_query(models.Task)
    return query.filter_by(**kwargs).all()
