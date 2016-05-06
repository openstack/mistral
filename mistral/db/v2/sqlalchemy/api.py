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

from oslo_config import cfg
from oslo_db import exception as db_exc
from oslo_db import sqlalchemy as oslo_sqlalchemy
from oslo_db.sqlalchemy import utils as db_utils
from oslo_log import log as logging
from oslo_utils import uuidutils
import sqlalchemy as sa

from mistral.db.sqlalchemy import base as b
from mistral.db.sqlalchemy import model_base as mb
from mistral.db.sqlalchemy import sqlite_lock
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
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
    # Expire all so all objects queried after lock is acquired
    # will be up-to-date from the DB and not from cache.
    session.expire_all()

    if b.get_driver_name() == 'sqlite':
        # In case of 'sqlite' we need to apply a manual lock.
        sqlite_lock.acquire_lock(id, session)

    return _lock_entity(model, id)


def _lock_entity(model, id):
    # Get entity by ID in "FOR UPDATE" mode and expect exactly one object.
    return _secure_query(model).with_for_update().filter(model.id == id).one()


def _secure_query(model, *columns):
    query = b.model_query(model, columns)

    shared_res_ids = []
    res_type = RESOURCE_MAPPING.get(model, '')

    if res_type:
        shared_res = _get_accepted_resources(res_type)
        shared_res_ids = [res.resource_id for res in shared_res]

    if issubclass(model, mb.MistralSecureModelBase):
        query = query.filter(
            sa.or_(
                model.project_id == security.get_project_id(),
                model.scope == 'public',
                model.id.in_(shared_res_ids)
            )
        )

    return query


def _paginate_query(model, limit=None, marker=None, sort_keys=None,
                    sort_dirs=None, query=None):
    if not query:
        query = _secure_query(model)

    query = db_utils.paginate_query(
        query,
        model,
        limit,
        sort_keys if sort_keys else {},
        marker=marker,
        sort_dirs=sort_dirs
    )

    return query.all()


def _delete_all(model, session=None, **kwargs):
    # NOTE(lane): Because we use 'in_' operator in _secure_query(), delete()
    # method will raise error with default parameter. Please refer to
    # http://docs.sqlalchemy.org/en/rel_1_0/orm/query.html#sqlalchemy.orm.query.Query.delete
    _secure_query(model).filter_by(**kwargs).delete(synchronize_session=False)


def _get_collection_sorted_by_name(model, **kwargs):
    # Note(lane): Sometimes tenant_A needs to get resources of tenant_B,
    # especially in resource sharing scenario, the resource owner needs to
    # check if the resource is used by a member.
    query = (b.model_query(model) if 'project_id' in kwargs
             else _secure_query(model))

    return query.filter_by(**kwargs).order_by(model.name).all()


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
        raise exc.DBEntityNotFoundException(
            "Workbook not found [workbook_name=%s]" % name
        )

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
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for WorkbookDefinition: %s" % e.columns
        )

    return wb


@b.session_aware()
def update_workbook(name, values, session=None):
    wb = _get_workbook(name)

    if not wb:
        raise exc.DBEntityNotFoundException(
            "Workbook not found [workbook_name=%s]" % name
        )

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
        raise exc.DBEntityNotFoundException(
            "Workbook not found [workbook_name=%s]" % name
        )

    session.delete(wb)


def _get_workbook(name):
    return _get_db_object_by_name(models.Workbook, name)


@b.session_aware()
def delete_workbooks(**kwargs):
    return _delete_all(models.Workbook, **kwargs)


# Workflow definitions.


WORKFLOW_COL_MAPPING = {
    'id': models.WorkflowDefinition.id,
    'name': models.WorkflowDefinition.name,
    'input': models.WorkflowDefinition.spec,
    'definition': models.WorkflowDefinition.definition,
    'tags': models.WorkflowDefinition.tags,
    'scope': models.WorkflowDefinition.scope,
    'created_at': models.WorkflowDefinition.created_at,
    'updated_at': models.WorkflowDefinition.updated_at
}


def get_workflow_definition(identifier):
    """Gets workflow definition by name or uuid.

    :param identifier: Identifier could be in the format of plain string or
                       uuid.
    :return: Workflow definition.
    """
    wf_def = (_get_workflow_definition_by_id(identifier)
              if uuidutils.is_uuid_like(identifier)
              else _get_workflow_definition(identifier))

    if not wf_def:
        raise exc.DBEntityNotFoundException(
            "Workflow not found [workflow_identifier=%s]" % identifier
        )

    return wf_def


def get_workflow_definition_by_id(id):
    wf_def = _get_workflow_definition_by_id(id)

    if not wf_def:
        raise exc.DBEntityNotFoundException(
            "Workflow not found [workflow_id=%s]" % id
        )

    return wf_def


def load_workflow_definition(name):
    return _get_workflow_definition(name)


def get_workflow_definitions(limit=None, marker=None, sort_keys=None,
                             sort_dirs=None, fields=None, **kwargs):
    columns = (
        tuple(WORKFLOW_COL_MAPPING.get(f) for f in fields) if fields else ()
    )

    query = _secure_query(models.WorkflowDefinition, *columns)

    try:
        return _paginate_query(
            models.WorkflowDefinition,
            limit,
            marker,
            sort_keys,
            sort_dirs,
            query
        )
    except Exception as e:
        raise exc.DBQueryEntryException(
            "Failed when querying database, error type: %s, "
            "error message: %s" % (e.__class__.__name__, e.message)
        )


@b.session_aware()
def create_workflow_definition(values, session=None):
    wf_def = models.WorkflowDefinition()

    wf_def.update(values.copy())

    try:
        wf_def.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for WorkflowDefinition: %s" % e.columns
        )

    return wf_def


@b.session_aware()
def update_workflow_definition(identifier, values, session=None):
    wf_def = get_workflow_definition(identifier)

    if wf_def.project_id != security.get_project_id():
        raise exc.NotAllowedException(
            "Can not update workflow of other tenants. "
            "[workflow_identifier=%s]" % identifier
        )

    if wf_def.is_system:
        raise exc.InvalidActionException(
            "Attempt to modify a system workflow: %s" % identifier
        )

    if wf_def.scope == 'public' and values['scope'] == 'private':
        cron_triggers = _get_associated_cron_triggers(identifier)

        try:
            [get_cron_trigger(name) for name in cron_triggers]
        except exc.DBEntityNotFoundException:
            raise exc.NotAllowedException(
                "Can not update scope of workflow that has triggers "
                "associated in other tenants."
                "[workflow_identifier=%s]" % identifier
            )

    wf_def.update(values.copy())

    return wf_def


@b.session_aware()
def create_or_update_workflow_definition(name, values, session=None):
    if not _get_workflow_definition(name):
        return create_workflow_definition(values)
    else:
        return update_workflow_definition(name, values)


@b.session_aware()
def delete_workflow_definition(identifier, session=None):
    wf_def = get_workflow_definition(identifier)

    if wf_def.project_id != security.get_project_id():
        raise exc.NotAllowedException(
            "Can not delete workflow of other users. [workflow_identifier=%s]"
            % identifier
        )

    if wf_def.is_system:
        msg = "Attempt to delete a system workflow: %s" % identifier
        raise exc.DataAccessException(msg)

    cron_triggers = _get_associated_cron_triggers(identifier)

    if cron_triggers:
        raise exc.DBException(
            "Can't delete workflow that has triggers associated. "
            "[workflow_identifier=%s], [cron_trigger_name(s)=%s]" %
            (identifier, ', '.join(cron_triggers))
        )

    # Delete workflow members first.
    delete_resource_members(resource_type='workflow', resource_id=wf_def.id)

    session.delete(wf_def)


def _get_associated_cron_triggers(wf_identifier):
    criterion = (
        {'workflow_id': wf_identifier}
        if uuidutils.is_uuid_like(wf_identifier)
        else {'workflow_name': wf_identifier}
    )

    cron_triggers = b.model_query(
        models.CronTrigger,
        [models.CronTrigger.name]
    ).filter_by(**criterion).all()

    return [t[0] for t in cron_triggers]


@b.session_aware()
def delete_workflow_definitions(**kwargs):
    return _delete_all(models.WorkflowDefinition, **kwargs)


def _get_workflow_definition(name):
    return _get_db_object_by_name(models.WorkflowDefinition, name)


def _get_workflow_definition_by_id(id):
    return _get_db_object_by_id(models.WorkflowDefinition, id)


# Action definitions.

def get_action_definition_by_id(id):
    action_def = _get_db_object_by_id(models.ActionDefinition, id)

    if not action_def:
        raise exc.DBEntityNotFoundException(
            "Action not found [action_id=%s]" % id
        )

    return action_def


def get_action_definition(name):
    a_def = _get_action_definition(name)

    if not a_def:
        raise exc.DBEntityNotFoundException(
            "Action definition not found [action_name=%s]" % name
        )

    return a_def


def load_action_definition(name):
    return _get_action_definition(name)


def get_action_definitions(limit=None, marker=None, sort_keys=['name'],
                           sort_dirs=None, **kwargs):
    query = _secure_query(models.ActionDefinition).filter_by(**kwargs)

    try:
        return _paginate_query(
            models.ActionDefinition,
            limit,
            marker,
            sort_keys,
            sort_dirs,
            query
        )
    except Exception as e:
        raise exc.DBQueryEntryException(
            "Failed when querying database, error type: %s, "
            "error message: %s" % (e.__class__.__name__, e.message)
        )


@b.session_aware()
def create_action_definition(values, session=None):
    a_def = models.ActionDefinition()

    a_def.update(values)

    try:
        a_def.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for action %s: %s" % (a_def.name, e.columns)
        )

    return a_def


@b.session_aware()
def update_action_definition(name, values, session=None):
    a_def = _get_action_definition(name)

    if not a_def:
        raise exc.DBEntityNotFoundException(
            "Action definition not found [action_name=%s]" % name
        )

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
        raise exc.DBEntityNotFoundException(
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
        raise exc.DBEntityNotFoundException(
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
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for Execution: %s" % e.columns
        )

    return ex


@b.session_aware()
def update_execution(id, values, session=None):
    ex = _get_execution(id)

    if not ex:
        raise exc.DBEntityNotFoundException(
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
        raise exc.DBEntityNotFoundException(
            "Execution not found [execution_id=%s]" % id
        )

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
        raise exc.DBEntityNotFoundException(
            "ActionExecution not found [id=%s]" % id
        )

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
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for ActionExecution: %s" % e.columns
        )

    return a_ex


@b.session_aware()
def update_action_execution(id, values, session=None):
    a_ex = _get_action_execution(id)

    if not a_ex:
        raise exc.DBEntityNotFoundException(
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
        raise exc.DBEntityNotFoundException(
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
        raise exc.DBEntityNotFoundException(
            "WorkflowExecution not found [id=%s]" % id
        )

    return wf_ex


def load_workflow_execution(id):
    return _get_workflow_execution(id)


def ensure_workflow_execution_exists(id):
    get_workflow_execution(id)


def get_workflow_executions(limit=None, marker=None, sort_keys=['created_at'],
                            sort_dirs=None, **kwargs):
    query = _secure_query(models.WorkflowExecution).filter_by(**kwargs)

    try:
        return _paginate_query(
            models.WorkflowExecution,
            limit,
            marker,
            sort_keys,
            sort_dirs,
            query
        )
    except Exception as e:
        raise exc.DBQueryEntryException(
            "Failed when quering database, error type: %s, "
            "error message: %s" % (e.__class__.__name__, e.message)
        )


@b.session_aware()
def create_workflow_execution(values, session=None):
    wf_ex = models.WorkflowExecution()

    wf_ex.update(values.copy())

    try:
        wf_ex.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for WorkflowExecution: %s" % e.columns
        )

    return wf_ex


@b.session_aware()
def update_workflow_execution(id, values, session=None):
    wf_ex = _get_workflow_execution(id)

    if not wf_ex:
        raise exc.DBEntityNotFoundException(
            "WorkflowExecution not found [id=%s]" % id
        )

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
        raise exc.DBEntityNotFoundException(
            "WorkflowExecution not found [id=%s]" % id
        )

    session.delete(wf_ex)


@b.session_aware()
def delete_workflow_executions(**kwargs):
    return _delete_all(models.WorkflowExecution, **kwargs)


def _get_workflow_execution(id):
    return _get_db_object_by_id(models.WorkflowExecution, id)


# Tasks executions.

def get_task_execution(id):
    task_ex = _get_task_execution(id)

    if not task_ex:
        raise exc.DBEntityNotFoundException(
            "Task execution not found [id=%s]" % id
        )

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
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for TaskExecution: %s" % e.columns
        )

    return task_ex


@b.session_aware()
def update_task_execution(id, values, session=None):
    task_ex = _get_task_execution(id)

    if not task_ex:
        raise exc.DBEntityNotFoundException(
            "TaskExecution not found [id=%s]" % id
        )

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
        raise exc.DBEntityNotFoundException(
            "TaskExecution not found [id=%s]" % id
        )

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
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for DelayedCall: %s" % e.columns
        )

    return delayed_call


@b.session_aware()
def delete_delayed_call(id, session=None):
    delayed_call = _get_delayed_call(id)

    if not delayed_call:
        raise exc.DBEntityNotFoundException(
            "DelayedCall not found [id=%s]" % id
        )

    session.delete(delayed_call)


@b.session_aware()
def get_delayed_calls_to_start(time, session=None):
    query = b.model_query(models.DelayedCall)

    query = query.filter(models.DelayedCall.execution_time < time)
    query = query.filter_by(processing=False)
    query = query.order_by(models.DelayedCall.execution_time)

    return query.all()


@b.session_aware()
def update_delayed_call(id, values, query_filter=None, session=None):
    if query_filter:
        try:
            specimen = models.DelayedCall(id=id, **query_filter)
            delayed_call = b.model_query(
                models.DelayedCall).update_on_match(specimen=specimen,
                                                    surrogate_key='id',
                                                    values=values)
            return delayed_call, 1

        except oslo_sqlalchemy.update_match.NoRowsMatched as e:
            LOG.debug(
                "No rows matched for update call [id=%s, values=%s, "
                "query_filter=%s,"
                "exception=%s]", id, values, query_filter, e
            )

            return None, 0

    else:
        delayed_call = get_delayed_call(id=id, session=session)
        delayed_call.update(values)

        return delayed_call, len(session.dirty)


@b.session_aware()
def get_delayed_call(id, session=None):
    delayed_call = _get_delayed_call(id=id, session=session)

    if not delayed_call:
        raise exc.DBEntityNotFoundException(
            "Delayed Call not found [id=%s]" % id
        )

    return delayed_call


@b.session_aware()
def get_expired_executions(time, session=None):
    query = b.model_query(models.WorkflowExecution)

    # Only WorkflowExecution that are not a child of other WorkflowExecution.
    query = query.filter(models.WorkflowExecution.
                         task_execution_id == sa.null())
    query = query.filter(models.WorkflowExecution.updated_at < time)
    query = query.filter(
        sa.or_(
            models.WorkflowExecution.state == "SUCCESS",
            models.WorkflowExecution.state == "ERROR"
        )
    )

    return query.all()


@b.session_aware()
def _get_delayed_call(id, session=None):
    query = b.model_query(models.DelayedCall)

    return query.filter_by(id=id).first()


# Cron triggers.

def get_cron_trigger(name):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        raise exc.DBEntityNotFoundException(
            "Cron trigger not found [name=%s]" % name
        )

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
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for cron trigger %s: %s"
            % (cron_trigger.name, e.columns)
        )
    # TODO(nmakhotkin): Remove this 'except' after fixing
    # https://bugs.launchpad.net/oslo.db/+bug/1458583.
    except db_exc.DBError as e:
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for cron trigger: %s" % e
        )

    return cron_trigger


@b.session_aware()
def update_cron_trigger(name, values, session=None, query_filter=None):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        raise exc.DBEntityNotFoundException(
            "Cron trigger not found [name=%s]" % name
        )

    if query_filter:
        try:
            # Execute the UPDATE statement with the query_filter as the WHERE.
            specimen = models.CronTrigger(id=cron_trigger.id, **query_filter)

            query = b.model_query(models.CronTrigger)

            cron_trigger = query.update_on_match(
                specimen=specimen,
                surrogate_key='id',
                values=values
            )

            return cron_trigger, 1

        except oslo_sqlalchemy.update_match.NoRowsMatched:
            LOG.debug(
                "No rows matched for cron update call"
                "[id=%s, values=%s, query_filter=%s", id, values, query_filter
            )

            return cron_trigger, 0

    else:
        cron_trigger.update(values.copy())

        return cron_trigger, len(session.dirty)


@b.session_aware()
def create_or_update_cron_trigger(name, values, session=None):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        return create_cron_trigger(values)
    else:
        updated, _ = update_cron_trigger(name, values)
        return updated


@b.session_aware()
def delete_cron_trigger(name, session=None):
    cron_trigger = _get_cron_trigger(name)

    if not cron_trigger:
        raise exc.DBEntityNotFoundException(
            "Cron trigger not found [name=%s]" % name
        )

    # Delete the cron trigger by ID and get the affected row count.
    table = models.CronTrigger.__table__
    result = session.execute(
        table.delete().where(table.c.id == cron_trigger.id)
    )

    return result.rowcount


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
        raise exc.DBEntityNotFoundException(
            "Environment not found [name=%s]" % name
        )

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
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for Environment: %s" % e.columns
        )

    return env


@b.session_aware()
def update_environment(name, values, session=None):
    env = _get_environment(name)

    if not env:
        raise exc.DBEntityNotFoundException(
            "Environment not found [name=%s]" % name
        )

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
        raise exc.DBEntityNotFoundException(
            "Environment not found [name=%s]" % name
        )

    session.delete(env)


def _get_environment(name):
    return _get_db_object_by_name(models.Environment, name)


@b.session_aware()
def delete_environments(**kwargs):
    return _delete_all(models.Environment, **kwargs)


# Resource members.


RESOURCE_MAPPING = {
    models.WorkflowDefinition: 'workflow',
    models.Workbook: 'workbook'
}


def _get_criterion(resource_id, member_id=None, is_owner=True):
    """Generates criterion for querying resource_member_v2 table."""

    # Resource owner query resource membership with member_id.
    if is_owner and member_id:
        return sa.and_(
            models.ResourceMember.project_id == security.get_project_id(),
            models.ResourceMember.resource_id == resource_id,
            models.ResourceMember.member_id == member_id
        )
    # Resource owner query resource memberships.
    elif is_owner and not member_id:
        return sa.and_(
            models.ResourceMember.project_id == security.get_project_id(),
            models.ResourceMember.resource_id == resource_id,
        )

    # Other members query other resource membership.
    elif not is_owner and member_id and member_id != security.get_project_id():
        return None

    # Resource member query resource memberships.
    return sa.and_(
        models.ResourceMember.member_id == security.get_project_id(),
        models.ResourceMember.resource_id == resource_id
    )


@b.session_aware()
def create_resource_member(values, session=None):
    res_member = models.ResourceMember()

    res_member.update(values.copy())

    try:
        res_member.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryException(
            "Duplicate entry for ResourceMember: %s" % e.columns
        )

    return res_member


def get_resource_member(resource_id, res_type, member_id):
    query = _secure_query(models.ResourceMember).filter_by(
        resource_type=res_type
    )

    # Both resource owner and resource member can do query.
    res_member = query.filter(
        sa.or_(
            _get_criterion(resource_id, member_id),
            _get_criterion(resource_id, member_id, is_owner=False)
        )
    ).first()

    if not res_member:
        raise exc.DBEntityNotFoundException(
            "Resource member not found [resource_id=%s, member_id=%s]" %
            (resource_id, member_id)
        )

    return res_member


def get_resource_members(resource_id, res_type):
    query = _secure_query(models.ResourceMember).filter_by(
        resource_type=res_type
    )

    # Both resource owner and resource member can do query.
    res_members = query.filter(
        sa.or_(
            _get_criterion(resource_id),
            _get_criterion(resource_id, is_owner=False),
        )
    ).all()

    return res_members


@b.session_aware()
def update_resource_member(resource_id, res_type, member_id, values,
                           session=None):
    # Only member who is not the owner of the resource can update the
    # membership status.
    if member_id != security.get_project_id():
        raise exc.DBEntityNotFoundException(
            "Resource member not found [resource_id=%s, member_id=%s]" %
            (resource_id, member_id)
        )

    query = _secure_query(models.ResourceMember).filter_by(
        resource_type=res_type
    )

    res_member = query.filter(
        _get_criterion(resource_id, member_id, is_owner=False)
    ).first()

    if not res_member:
        raise exc.DBEntityNotFoundException(
            "Resource member not found [resource_id=%s, member_id=%s]" %
            (resource_id, member_id)
        )

    res_member.update(values.copy())

    return res_member


@b.session_aware()
def delete_resource_member(resource_id, res_type, member_id, session=None):
    query = _secure_query(models.ResourceMember).filter_by(
        resource_type=res_type
    )

    res_member = query.filter(_get_criterion(resource_id, member_id)).first()

    if not res_member:
        raise exc.DBEntityNotFoundException(
            "Resource member not found [resource_id=%s, member_id=%s]" %
            (resource_id, member_id)
        )

    # TODO(lane): Check association with cron triggers when deleting a workflow
    # member which is in 'accepted' status.

    session.delete(res_member)


@b.session_aware()
def delete_resource_members(**kwargs):
    return _delete_all(models.ResourceMember, **kwargs)


def _get_accepted_resources(res_type):
    resources = _secure_query(models.ResourceMember).filter(
        sa.and_(
            models.ResourceMember.resource_type == res_type,
            models.ResourceMember.status == 'accepted',
            models.ResourceMember.member_id == security.get_project_id()
        )
    ).all()

    return resources
