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
        # TODO(rakhmerov): How to setup for multiple versions?
        models.Workbook.metadata.drop_all(b.get_engine())
        _facade = None
    except Exception as e:
        raise exc.DBException("Failed to drop database: %s" + e)


# Transaction management.

def start_tx():
    b.start_tx()


def commit_tx():
    b.commit_tx()


def rollback_tx():
    b.rollback_tx()


def end_tx():
    b.end_tx()


# Workbooks.

def get_workbook(name):
    wb = _get_workbook(name)

    if not wb:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % name)

    return wb


def get_workbooks(**kwargs):
    return _get_workbooks(**kwargs)


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
def delete_workbook(name, session=None):
    wb = _get_workbook(name)

    if not wb:
        raise exc.NotFoundException(
            "Workbook not found [workbook_name=%s]" % name)

    session.delete(wb)


def _get_workbooks(**kwargs):
    query = b.model_query(models.Workbook)
    proj = query.filter_by(project_id=context.ctx().project_id,
                           **kwargs)
    public = query.filter_by(scope='public', **kwargs)

    return proj.union(public).all()


def _get_workbook(name):
    query = b.model_query(models.Workbook)

    return query.filter_by(name=name,
                           project_id=context.ctx().project_id).first()


# Workflows.

def get_workflow(name):
    wf = _get_workflow(name)

    if not wf:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name)

    return wf


def get_workflows(**kwargs):
    return _get_workflows(**kwargs)


@b.session_aware()
def create_workflow(values, session=None):
    wf = models.Workflow()

    wf.update(values.copy())
    wf['project_id'] = context.ctx().project_id

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
    wf['project_id'] = context.ctx().project_id

    return wf


@b.session_aware()
def delete_workflow(name, session=None):
    wf = _get_workflow(name)

    if not wf:
        raise exc.NotFoundException(
            "Workflow not found [workflow_name=%s]" % name)

    session.delete(wf)


def _get_workflows(**kwargs):
    query = b.model_query(models.Workflow)
    proj = query.filter_by(project_id=context.ctx().project_id,
                           **kwargs)
    public = query.filter_by(scope='public', **kwargs)

    return proj.union(public).all()


def _get_workflow(name):
    query = b.model_query(models.Workflow)

    return query.filter_by(name=name,
                           project_id=context.ctx().project_id).first()


# Executions.

def get_execution(id):
    execution = _get_execution(id)

    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id)

    return execution


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
def delete_execution(id, session=None):
    execution = _get_execution(id)

    if not execution:
        raise exc.NotFoundException(
            "Execution not found [execution_id=%s]" % id)

    session.delete(execution)


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
def delete_task(id, session=None):
    task = _get_task(id)

    if not task:
        raise exc.NotFoundException(
            "Task not found [task_id=%s]" % id)

    session.delete(task)


def _get_task(id):
    query = b.model_query(models.Task)

    return query.filter_by(id=id).first()


def _get_tasks(**kwargs):
    query = b.model_query(models.Task)

    return query.filter_by(**kwargs).all()
