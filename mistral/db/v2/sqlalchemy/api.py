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
from mistral.db.v2.sqlalchemy import models
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
    query = b.model_query(model).filter_by(**kwargs)
    query.delete()


def _get_collection_sorted_by_name(model, **kwargs):
    query = b.model_query(model)

    proj = query.filter_by(project_id=context.ctx().project_id, **kwargs)
    public = query.filter_by(scope='public', **kwargs)

    return proj.union(public).order_by(model.name).all()


# Workbooks.

def get_workbook(name):
    wb = _get_workbook(name)

    if not wb:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % name)

    return wb


def load_workbook(name):
    return _get_workbook(name)


def get_workbooks(**kwargs):
    return _get_collection_sorted_by_name(models.Workbook, **kwargs)


@b.session_aware()
def create_workbook(values, session=None):
    wb = models.Workbook()

    wb.update(values.copy())
    wb['project_id'] = context.ctx().project_id

    try:
        wb.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Workbook: %s"
                                   % e.columns)

    return wb


@b.session_aware()
def update_workbook(name, values, session=None):
    wb = _get_workbook(name)

    if not wb:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % name)

    wb.update(values.copy())
    wb['project_id'] = context.ctx().project_id

    return wb


@b.session_aware()
def create_or_update_workbook(name, values, session=None):
    wb = _get_workbook(name)

    if not wb:
        return create_workbook(values)
    else:
        return update_workbook(name, values)


@b.session_aware()
def delete_workbook(name, session=None):
    wb = _get_workbook(name)

    if not wb:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % name)

    session.delete(wb)


def _get_workbook(name):
    query = b.model_query(models.Workbook)

    project_id = context.ctx().project_id if context.has_ctx() else None

    proj = query.filter_by(name=name, project_id=project_id)
    public = query.filter_by(name=name, scope='public')

    return proj.union(public).first()


@b.session_aware()
def delete_workbooks(**kwargs):
    return _delete_all(models.Workbook, **kwargs)


# Workflows.

def get_workflow(name):
    wf = _get_workflow(name)

    if not wf:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name)

    return wf


def load_workflow(name):
    return _get_workflow(name)


def get_workflows(**kwargs):
    return _get_collection_sorted_by_name(models.Workflow, **kwargs)


@b.session_aware()
def create_workflow(values, session=None):
    wf = models.Workflow()

    wf.update(values.copy())
    wf['project_id'] = context.ctx().project_id if context.has_ctx() else None

    try:
        wf.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for workflow: %s"
                                   % e.columns)

    return wf


@b.session_aware()
def update_workflow(name, values, session=None):
    wf = _get_workflow(name)

    if not wf:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name)

    wf.update(values.copy())
    wf['project_id'] = context.ctx().project_id if context.has_ctx() else None

    return wf


@b.session_aware()
def create_or_update_workflow(name, values, session=None):
    wf = _get_workflow(name)

    if not wf:
        return create_workflow(values)
    else:
        return update_workflow(name, values)


@b.session_aware()
def delete_workflow(name, session=None):
    wf = _get_workflow(name)

    if not wf:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name)

    session.delete(wf)


@b.session_aware()
def delete_workflows(**kwargs):
    return _delete_all(models.Workflow, **kwargs)


def _get_workflow(name):
    query = b.model_query(models.Workflow)

    project_id = context.ctx().project_id if context.has_ctx() else None

    proj = query.filter_by(name=name, project_id=project_id)
    public = query.filter_by(name=name, scope='public')

    return proj.union(public).first()


# Executions.

def get_execution(id):
    execution = _get_execution(id)

    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id)

    return execution


def load_execution(id):
    return _get_execution(id)


def ensure_execution_exists(id):
    get_execution(id)


def get_executions(**kwargs):
    return _get_executions(**kwargs)


@b.session_aware()
def create_execution(values, session=None):
    execution = models.Execution()

    execution.update(values.copy())

    try:
        execution.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Execution: %s"
                                   % e.columns)

    return execution


@b.session_aware()
def update_execution(id, values, session=None):
    execution = _get_execution(id)

    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id)

    execution.update(values.copy())

    return execution


@b.session_aware()
def create_or_update_execution(id, values, session=None):
    execution = _get_execution(id)

    if not execution:
        return create_execution(values)
    else:
        return update_execution(id, values)


@b.session_aware()
def delete_execution(id, session=None):
    execution = _get_execution(id)

    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id)

    session.delete(execution)


@b.session_aware()
def delete_executions(**kwargs):
    _delete_all(models.Task)
    return _delete_all(models.Execution, **kwargs)


def _get_executions(**kwargs):
    query = b.model_query(models.Execution)

    return query.filter_by(**kwargs).all()


def _get_execution(id):
    query = b.model_query(models.Execution)

    return query.filter_by(id=id).first()


# Tasks.

def get_task(id):
    task = _get_task(id)

    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % id)

    return task


def load_task(id):
    return _get_task(id)


def get_tasks(**kwargs):
    return _get_tasks(**kwargs)


@b.session_aware()
def create_task(values, session=None):
    task = models.Task()

    task.update(values)

    try:
        task.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for Task: %s"
                                   % e.columns)

    return task


@b.session_aware()
def update_task(id, values, session=None):
    task = _get_task(id)

    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % id)

    task.update(values.copy())

    return task


@b.session_aware()
def create_or_update_task(id, values, session=None):
    task = _get_task(id)

    if not task:
        return create_task(values)
    else:
        return update_task(id, values)


@b.session_aware()
def delete_task(id, session=None):
    task = _get_task(id)

    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % id)

    session.delete(task)


@b.session_aware()
def delete_tasks(**kwargs):
    return _delete_all(models.Task, **kwargs)


def _get_task(id):
    query = b.model_query(models.Task)

    return query.filter_by(id=id).first()


def _get_tasks(**kwargs):
    query = b.model_query(models.Task)

    return query.filter_by(**kwargs).all()


# Delayed calls.

@b.session_aware()
def create_delayed_call(values, session=None):
    delayed_call = models.DelayedCall()
    delayed_call.update(values.copy())

    try:
        delayed_call.save(session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for DelayedCall: %s"
                                   % e.columns)

    return delayed_call


@b.session_aware()
def delete_delayed_call(delayed_call_id, session=None):
    delayed_call = _get_delayed_call(delayed_call_id)
    if not delayed_call:
        raise exc.NotFoundException("DelayedCall not found [delayed_call_id="
                                    "%s]" % delayed_call_id)

    session.delete(delayed_call)


@b.session_aware()
def get_delayed_calls_to_start(time, session=None):
    query = b.model_query(models.DelayedCall)
    query = query.filter(models.DelayedCall.execution_time < time)
    query = query.order_by(models.DelayedCall.execution_time)

    return query.all()


@b.session_aware()
def _get_delayed_call(delayed_call_id, session=None):
    query = b.model_query(models.DelayedCall)

    return query.filter_by(id=delayed_call_id).first()


# Actions.

def get_action(name):
    action = _get_action(name)

    if not action:
        raise exc.NotFoundException(
            "Action not found [action_name=%s]" % name)

    return action


def load_action(name):
    return _get_action(name)


def get_actions(**kwargs):
    return _get_collection_sorted_by_name(models.Action, **kwargs)


@b.session_aware()
def create_action(values, session=None):
    action = models.Action()

    action.update(values)

    try:
        action.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for action %s: %s"
                                   % (action.name, e.columns))

    return action


@b.session_aware()
def update_action(name, values, session=None):
    action = _get_action(name)

    if not action:
        raise exc.NotFoundException(
            "Action not found [action_name=%s]" % name)

    action.update(values.copy())

    return action


@b.session_aware()
def create_or_update_action(name, values, session=None):
    action = _get_action(name)

    if not action:
        return create_action(values)
    else:
        return update_action(name, values)


@b.session_aware()
def delete_action(name, session=None):
    action = _get_action(name)

    if not action:
        raise exc.NotFoundException(
            "Action not found [action_name=%s]" % name)

    session.delete(action)


@b.session_aware()
def delete_actions(**kwargs):
    return _delete_all(models.Action, **kwargs)


def _get_action(name):
    query = b.model_query(models.Action)

    return query.filter_by(name=name).first()


def _get_actions(**kwargs):
    query = b.model_query(models.Action)

    return query.filter_by(**kwargs).all()


# Cron triggers.

def get_cron_trigger(name):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        raise exc.NotFoundException(
            "Cron trigger not found [name=%s]" % name)

    return cron_trigger


def load_cron_trigger(name):
    return _get_cron_trigger(name)


def get_cron_triggers(**kwargs):
    return _get_collection_sorted_by_name(models.CronTrigger, **kwargs)


@b.session_aware()
def get_next_cron_triggers(time, session=None):
    query = b.model_query(models.CronTrigger)

    query = query.filter(models.CronTrigger.next_execution_time < time)
    query = query.order_by(models.CronTrigger.next_execution_time)

    return query.all()


@b.session_aware()
def create_cron_trigger(values, session=None):
    cron_trigger = models.CronTrigger()

    cron_trigger.update(values)

    try:
        cron_trigger.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry("Duplicate entry for cron trigger %s: %s"
                                   % (cron_trigger.name, e.columns))

    return cron_trigger


@b.session_aware()
def update_cron_trigger(name, values, session=None):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        raise exc.NotFoundException(
            "Cron trigger not found [name=%s]" % name)

    cron_trigger.update(values.copy())

    return cron_trigger


@b.session_aware()
def create_or_update_cron_trigger(name, values, session=None):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        return create_cron_trigger(values)
    else:
        return update_cron_trigger(name, values)


@b.session_aware()
def delete_cron_trigger(name, session=None):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        raise exc.NotFoundException(
            "Cron trigger not found [name=%s]" % name)

    session.delete(cron_trigger)


@b.session_aware()
def delete_cron_triggers(**kwargs):
    return _delete_all(models.CronTrigger, **kwargs)


def _get_cron_trigger(name):
    query = b.model_query(models.CronTrigger)

    return query.filter_by(name=name).first()


def _get_cron_triggers(**kwargs):
    query = b.model_query(models.CronTrigger)

    return query.filter_by(**kwargs).all()
