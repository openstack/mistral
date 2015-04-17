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

import contextlib
import sys

from oslo.config import cfg
from oslo.db import exception as db_exc
from oslo.utils import timeutils
import sqlalchemy as sa

from mistral.db.sqlalchemy import base as b
from mistral.db.sqlalchemy import model_base as mb
from mistral.db.sqlalchemy import sqlite_lock
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.services import security

CONF = cfg.CONF
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


@b.session_aware()
def acquire_lock(model, id, session=None):
    if b.get_driver_name() != 'sqlite':
        query = _secure_query(model).filter("id = '%s'" % id)

        query.update(
            {'updated_at': timeutils.utcnow()},
            synchronize_session=False
        )
    else:
        sqlite_lock.acquire_lock(id, session)


def _secure_query(model):
    query = b.model_query(model)

    if issubclass(model, mb.MistralSecureModelBase):
        query = query.filter(
            sa.or_(
                model.project_id == security.get_project_id(),
                model.scope == 'public'
            )
        )

    return query


def _delete_all(model, session=None, **kwargs):
    _secure_query(model).filter_by(**kwargs).delete()


def _get_collection_sorted_by_name(model, **kwargs):
    return _secure_query(model).filter_by(**kwargs).order_by(model.name).all()


def _get_collection_sorted_by_time(model, **kwargs):
    query = _secure_query(model)

    return query.filter_by(**kwargs).order_by(model.created_at).all()


def _get_db_object_by_name(model, name):
    return _secure_query(model).filter_by(name=name).first()


def _get_db_object_by_id(model, id):
    return _secure_query(model).filter_by(id=id).first()


# Workbook definitions.

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

    try:
        wb.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for WorkbookDefinition: %s" % e.columns
        )

    return wb


@b.session_aware()
def update_workbook(name, values, session=None):
    wb = _get_workbook(name)

    if not wb:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % name)

    wb.update(values.copy())

    return wb


@b.session_aware()
def create_or_update_workbook(name, values, session=None):
    if not _get_workbook(name):
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
    return _get_db_object_by_name(models.Workbook, name)


@b.session_aware()
def delete_workbooks(**kwargs):
    return _delete_all(models.Workbook, **kwargs)


# Workflow definitions.

def get_workflow_definition(name):
    wf_def = _get_workflow_definition(name)

    if not wf_def:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name
        )

    return wf_def


def load_workflow_definition(name):
    return _get_workflow_definition(name)


def get_workflow_definitions(**kwargs):
    return _get_collection_sorted_by_name(models.WorkflowDefinition, **kwargs)


@b.session_aware()
def create_workflow_definition(values, session=None):
    wf_def = models.WorkflowDefinition()

    wf_def.update(values.copy())

    try:
        wf_def.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for WorkflowDefinition: %s" % e.columns
        )

    return wf_def


@b.session_aware()
def update_workflow_definition(name, values, session=None):
    wf_def = _get_workflow_definition(name)

    if not wf_def:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name)

    wf_def.update(values.copy())

    return wf_def


@b.session_aware()
def create_or_update_workflow_definition(name, values, session=None):
    if not _get_workflow_definition(name):
        return create_workflow_definition(values)
    else:
        return update_workflow_definition(name, values)


@b.session_aware()
def delete_workflow_definition(name, session=None):
    wf_def = _get_workflow_definition(name)

    if not wf_def:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name
        )

    session.delete(wf_def)


@b.session_aware()
def delete_workflow_definitions(**kwargs):
    return _delete_all(models.WorkflowDefinition, **kwargs)


def _get_workflow_definition(name):
    return _get_db_object_by_name(models.WorkflowDefinition, name)


# Action definitions.

def get_action_definition(name):
    a_def = _get_action_definition(name)

    if not a_def:
        raise exc.NotFoundException(
            "Action definition not found [action_name=%s]" % name
        )

    return a_def


def load_action_definition(name):
    return _get_action_definition(name)


def get_action_definitions(**kwargs):
    return _get_collection_sorted_by_name(models.ActionDefinition, **kwargs)


@b.session_aware()
def create_action_definition(values, session=None):
    a_def = models.ActionDefinition()

    a_def.update(values)

    try:
        a_def.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for action %s: %s" % (a_def.name, e.columns)
        )

    return a_def


@b.session_aware()
def update_action_definition(name, values, session=None):
    a_def = _get_action_definition(name)

    if not a_def:
        raise exc.NotFoundException(
            "Action definition not found [action_name=%s]" % name)

    a_def.update(values.copy())

    return a_def


@b.session_aware()
def create_or_update_action_definition(name, values, session=None):
    if not _get_action_definition(name):
        return create_action_definition(values)
    else:
        return update_action_definition(name, values)


@b.session_aware()
def delete_action_definition(name, session=None):
    a_def = _get_action_definition(name)

    if not a_def:
        raise exc.NotFoundException(
            "Action definition not found [action_name=%s]" % name
        )

    session.delete(a_def)


@b.session_aware()
def delete_action_definitions(**kwargs):
    return _delete_all(models.ActionDefinition, **kwargs)


def _get_action_definition(name):
    return _get_db_object_by_name(models.ActionDefinition, name)


# Common executions.

def get_execution(id):
    ex = _get_execution(id)

    if not ex:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id
        )

    return ex


def load_execution(id):
    return _get_execution(id)


def ensure_execution_exists(id):
    get_execution(id)


def get_executions(**kwargs):
    return _get_executions(**kwargs)


@b.session_aware()
def create_execution(values, session=None):
    ex = models.Execution()

    ex.update(values.copy())

    try:
        ex.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for Execution: %s" % e.columns
        )

    return ex


@b.session_aware()
def update_execution(id, values, session=None):
    ex = _get_execution(id)

    if not ex:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id
        )

    ex.update(values.copy())

    return ex


@b.session_aware()
def create_or_update_execution(id, values, session=None):
    if not _get_execution(id):
        return create_execution(values)
    else:
        return update_execution(id, values)


@b.session_aware()
def delete_execution(id, session=None):
    ex = _get_execution(id)

    if not ex:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id)

    session.delete(ex)


@b.session_aware()
def delete_executions(**kwargs):
    return _delete_all(models.Execution, **kwargs)


def _get_executions(**kwargs):
    return _get_collection_sorted_by_time(models.Execution, **kwargs)


def _get_execution(id):
    return _get_db_object_by_id(models.Execution, id)


# Action executions.

def get_action_execution(id):
    a_ex = _get_action_execution(id)

    if not a_ex:
        raise exc.NotFoundException(
            "ActionExecution not found [id=%s]" % id)

    return a_ex


def load_action_execution(id):
    return _get_action_execution(id)


def ensure_action_execution_exists(id):
    get_action_execution(id)


def get_action_executions(**kwargs):
    return _get_action_executions(**kwargs)


@b.session_aware()
def create_action_execution(values, session=None):
    a_ex = models.ActionExecution()

    a_ex.update(values.copy())

    try:
        a_ex.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for ActionExecution: %s" % e.columns
        )

    return a_ex


@b.session_aware()
def update_action_execution(id, values, session=None):
    a_ex = _get_action_execution(id)

    if not a_ex:
        raise exc.NotFoundException(
            "ActionExecution not found [id=%s]" % id
        )

    a_ex.update(values.copy())

    return a_ex


@b.session_aware()
def create_or_update_action_execution(id, values, session=None):
    if not _get_action_execution(id):
        return create_action_execution(values)
    else:
        return update_action_execution(id, values)


@b.session_aware()
def delete_action_execution(id, session=None):
    a_ex = _get_action_execution(id)

    if not a_ex:
        raise exc.NotFoundException(
            "ActionExecution not found [id=%s]" % id
        )

    session.delete(a_ex)


@b.session_aware()
def delete_action_executions(**kwargs):
    return _delete_all(models.ActionExecution, **kwargs)


def _get_action_executions(**kwargs):
    return _get_collection_sorted_by_time(models.ActionExecution, **kwargs)


def _get_action_execution(id):
    return _get_db_object_by_id(models.ActionExecution, id)


# Workflow executions.

def get_workflow_execution(id):
    wf_ex = _get_workflow_execution(id)

    if not wf_ex:
        raise exc.NotFoundException("WorkflowExecution not found [id=%s]" % id)

    return wf_ex


def load_workflow_execution(id):
    return _get_workflow_execution(id)


def ensure_workflow_execution_exists(id):
    get_workflow_execution(id)


def get_workflow_executions(**kwargs):
    return _get_workflow_executions(**kwargs)


@b.session_aware()
def create_workflow_execution(values, session=None):
    wf_ex = models.WorkflowExecution()

    wf_ex.update(values.copy())

    try:
        wf_ex.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for WorkflowExecution: %s" % e.columns
        )

    return wf_ex


@b.session_aware()
def update_workflow_execution(id, values, session=None):
    wf_ex = _get_workflow_execution(id)

    if not wf_ex:
        raise exc.NotFoundException("WorkflowExecution not found [id=%s]" % id)

    wf_ex.update(values.copy())

    return wf_ex


@b.session_aware()
def create_or_update_workflow_execution(id, values, session=None):
    if not _get_workflow_execution(id):
        return create_workflow_execution(values)
    else:
        return update_workflow_execution(id, values)


@b.session_aware()
def delete_workflow_execution(id, session=None):
    wf_ex = _get_workflow_execution(id)

    if not wf_ex:
        raise exc.NotFoundException("WorkflowExecution not found [id=%s]" % id)

    session.delete(wf_ex)


@b.session_aware()
def delete_workflow_executions(**kwargs):
    return _delete_all(models.WorkflowExecution, **kwargs)


def _get_workflow_executions(**kwargs):
    return _get_collection_sorted_by_time(models.WorkflowExecution, **kwargs)


def _get_workflow_execution(id):
    return _get_db_object_by_id(models.WorkflowExecution, id)


# Tasks executions.

def get_task_execution(id):
    task_ex = _get_task_execution(id)

    if not task_ex:
        raise exc.NotFoundException("Task execution not found [id=%s]" % id)

    return task_ex


def load_task_execution(id):
    return _get_task_execution(id)


def get_task_executions(**kwargs):
    return _get_task_executions(**kwargs)


@b.session_aware()
def create_task_execution(values, session=None):
    task_ex = models.TaskExecution()

    task_ex.update(values)

    try:
        task_ex.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for TaskExecution: %s" % e.columns
        )

    return task_ex


@b.session_aware()
def update_task_execution(id, values, session=None):
    task_ex = _get_task_execution(id)

    if not task_ex:
        raise exc.NotFoundException("TaskExecution not found [id=%s]" % id)

    task_ex.update(values.copy())

    return task_ex


@b.session_aware()
def create_or_update_task_execution(id, values, session=None):
    if not _get_task_execution(id):
        return create_task_execution(values)
    else:
        return update_task_execution(id, values)


@b.session_aware()
def delete_task_execution(id, session=None):
    task_ex = _get_task_execution(id)

    if not task_ex:
        raise exc.NotFoundException("TaskExecution not found [id=%s]" % id)

    session.delete(task_ex)


@b.session_aware()
def delete_task_executions(**kwargs):
    return _delete_all(models.TaskExecution, **kwargs)


def _get_task_execution(id):
    return _get_db_object_by_id(models.TaskExecution, id)


def _get_task_executions(**kwargs):
    return _get_collection_sorted_by_time(models.TaskExecution, **kwargs)


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
def delete_delayed_call(id, session=None):
    delayed_call = _get_delayed_call(id)

    if not delayed_call:
        raise exc.NotFoundException(
            "DelayedCall not found [id=%s]" % id
        )

    session.delete(delayed_call)


@b.session_aware()
def get_delayed_calls_to_start(time, session=None):
    query = b.model_query(models.DelayedCall)

    query = query.filter(models.DelayedCall.execution_time < time)
    query = query.order_by(models.DelayedCall.execution_time)

    return query.all()


@b.session_aware()
def _get_delayed_call(id, session=None):
    query = b.model_query(models.DelayedCall)

    return query.filter_by(id=id).first()


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
        raise exc.DBDuplicateEntry(
            "Duplicate entry for cron trigger %s: %s"
            % (cron_trigger.name, e.columns)
        )

    return cron_trigger


@b.session_aware()
def update_cron_trigger(name, values, session=None):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        raise exc.NotFoundException("Cron trigger not found [name=%s]" % name)

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
        raise exc.NotFoundException("Cron trigger not found [name=%s]" % name)

    session.delete(cron_trigger)


@b.session_aware()
def delete_cron_triggers(**kwargs):
    return _delete_all(models.CronTrigger, **kwargs)


def _get_cron_trigger(name):
    return _get_db_object_by_name(models.CronTrigger, name)


def _get_cron_triggers(**kwargs):
    query = b.model_query(models.CronTrigger)

    return query.filter_by(**kwargs).all()


# Environments.

def get_environment(name):
    env = _get_environment(name)

    if not env:
        raise exc.NotFoundException("Environment not found [name=%s]" % name)

    return env


def load_environment(name):
    return _get_environment(name)


def get_environments(**kwargs):
    return _get_collection_sorted_by_name(models.Environment, **kwargs)


@b.session_aware()
def create_environment(values, session=None):
    env = models.Environment()

    env.update(values)

    try:
        env.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntry(
            "Duplicate entry for Environment: %s" % e.columns
        )

    return env


@b.session_aware()
def update_environment(name, values, session=None):
    env = _get_environment(name)

    if not env:
        raise exc.NotFoundException("Environment not found [name=%s]" % name)

    env.update(values)

    return env


@b.session_aware()
def create_or_update_environment(name, values, session=None):
    env = _get_environment(name)

    if not env:
        return create_environment(values)
    else:
        return update_environment(name, values)


@b.session_aware()
def delete_environment(name, session=None):
    env = _get_environment(name)

    if not env:
        raise exc.NotFoundException("Environment not found [name=%s]" % name)

    session.delete(env)


def _get_environment(name):
    return _get_db_object_by_name(models.Environment, name)


@b.session_aware()
def delete_environments(**kwargs):
    return _delete_all(models.Environment, **kwargs)
