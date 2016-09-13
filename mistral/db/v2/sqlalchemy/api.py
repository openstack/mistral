# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
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
from oslo_utils import uuidutils  # noqa
import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Insert

from mistral.db.sqlalchemy import base as b
from mistral.db.sqlalchemy import model_base as mb
from mistral.db.sqlalchemy import sqlite_lock
from mistral.db.v2.sqlalchemy import filters as db_filters
from mistral.db.v2.sqlalchemy import models
from mistral import exceptions as exc
from mistral.services import security
from mistral import utils


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
        raise exc.DBError("Failed to setup database: %s" % e)


def drop_db():
    global _facade

    try:
        models.Workbook.metadata.drop_all(b.get_engine())
        _facade = None
    except Exception as e:
        raise exc.DBError("Failed to drop database: %s" % e)


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

    if not issubclass(model, mb.MistralSecureModelBase):
        return query

    shared_res_ids = []
    res_type = RESOURCE_MAPPING.get(model, '')

    if res_type:
        shared_res = _get_accepted_resources(res_type)
        shared_res_ids = [res.resource_id for res in shared_res]

    query_criterion = sa.or_(
        model.project_id == security.get_project_id(),
        model.scope == 'public'
    )

    # NOTE(kong): Include IN_ predicate in query filter only if shared_res_ids
    # is not empty to avoid sqlalchemy SAWarning and wasting a db call.
    if shared_res_ids:
        query_criterion = sa.or_(
            query_criterion,
            model.id.in_(shared_res_ids)
        )

    query = query.filter(query_criterion)

    return query


def _paginate_query(model, limit=None, marker=None, sort_keys=None,
                    sort_dirs=None, query=None):
    if not query:
        query = _secure_query(model)

    sort_keys = sort_keys if sort_keys else []

    if 'id' not in sort_keys:
        sort_keys.append('id')
        sort_dirs.append('asc') if sort_dirs else None

    query = db_utils.paginate_query(
        query,
        model,
        limit,
        sort_keys,
        marker=marker,
        sort_dirs=sort_dirs
    )

    return query


def _delete_all(model, session=None, **kwargs):
    # NOTE(kong): Because we use 'in_' operator in _secure_query(), delete()
    # method will raise error with default parameter. Please refer to
    # http://docs.sqlalchemy.org/en/rel_1_0/orm/query.html#sqlalchemy.orm.query.Query.delete
    _secure_query(model).filter_by(**kwargs).delete(synchronize_session=False)


def _get_collection(model, insecure=False, limit=None, marker=None,
                    sort_keys=None, sort_dirs=None, fields=None, **filters):
    columns = (
        tuple([getattr(model, f) for f in fields if hasattr(model, f)])
        if fields else ()
    )

    query = (b.model_query(model, *columns) if insecure
             else _secure_query(model, *columns))
    query = db_filters.apply_filters(query, model, **filters)

    query = _paginate_query(
        model,
        limit,
        marker,
        sort_keys,
        sort_dirs,
        query
    )

    try:
        return query.all()
    except Exception as e:
        raise exc.DBQueryEntryError(
            "Failed when querying database, error type: %s, "
            "error message: %s" % (e.__class__.__name__, str(e))
        )


def _get_collection_sorted_by_name(model, insecure=False, fields=None,
                                   sort_keys=['name'], **kwargs):
    return _get_collection(
        model=model,
        insecure=insecure,
        sort_keys=sort_keys,
        fields=fields,
        **kwargs
    )


def _get_collection_sorted_by_time(model, insecure=False, fields=None,
                                   sort_keys=['created_at'], **kwargs):
    return _get_collection(
        model=model,
        insecure=insecure,
        sort_keys=sort_keys,
        fields=fields,
        **kwargs
    )


def _get_db_object_by_name(model, name):
    return _secure_query(model).filter_by(name=name).first()


def _get_db_object_by_id(model, id):
    return _secure_query(model).filter_by(id=id).first()


def _get_db_object_by_name_or_id(model, identifier):
    query = _secure_query(model)
    query = query.filter(
        sa.or_(
            model.id == identifier,
            model.name == identifier
        )
    )

    return query.first()


@compiles(Insert)
def append_string(insert, compiler, **kw):
    s = compiler.visit_insert(insert, **kw)

    if 'append_string' in insert.kwargs:
        append = insert.kwargs['append_string']

        if append:
            s += " " + append

    if 'replace_string' in insert.kwargs:
        replace = insert.kwargs['replace_string']

        if isinstance(replace, tuple):
            s = s.replace(replace[0], replace[1])

    return s


@b.session_aware()
def insert_or_ignore(model_cls, values, session=None):
    """Insert a new object into DB or ignore if it already exists.

    This method is based on ability of MySQL, PostgreSQL and SQLite
    to check unique constraint violations and allow user to take a
    conflict mitigation action. Hence, uniqueness of the object that's
    being inserted should be considered only from this perspective.

    Note: This method hasn't been tested on databases other than MySQL,
    PostgreSQL 9.5 or later, and SQLite. Therefore there's no guarantee
    that it will work with them.

    :param model_cls: Model class.
    :param values: Values of the new object.
    """

    model = model_cls()

    model.update(values)

    append = None
    replace = None

    dialect = b.get_dialect_name()

    if dialect == 'sqlite':
        replace = ('INSERT INTO', 'INSERT OR IGNORE INTO')
    elif dialect == 'mysql':
        append = 'ON DUPLICATE KEY UPDATE id=id'
    elif dialect == 'postgres':
        append = 'ON CONFLICT DO NOTHING'
    else:
        raise RuntimeError(
            '"Insert or ignore" is supported only for dialects: sqlite,'
            ' mysql and postgres. Actual dialect: %s' % dialect
        )

    insert = model.__table__.insert(
        append_string=append,
        replace_string=replace
    )

    # NOTE(rakhmerov): As it turned out the result proxy object
    # returned by insert expression does not provide a valid
    # count of updated rows in for all supported databases.
    # For this reason we shouldn't return anything from this
    # method. In order to check whether a new object was really
    # inserted users should rely on different approaches. The
    # simplest is just to insert an object with an explicitly
    # set id and then check if object with such id exists in DB.
    # Generated id must be unique to make it work.
    session.execute(insert, model.to_dict())


# Workbook definitions.

def get_workbook(name):
    wb = _get_db_object_by_name(models.Workbook, name)

    if not wb:
        raise exc.DBEntityNotFoundError(
            "Workbook not found [workbook_name=%s]" % name
        )

    return wb


def load_workbook(name):
    return _get_db_object_by_name(models.Workbook, name)


def get_workbooks(**kwargs):
    return _get_collection_sorted_by_name(models.Workbook, **kwargs)


@b.session_aware()
def create_workbook(values, session=None):
    wb = models.Workbook()

    wb.update(values.copy())

    try:
        wb.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for WorkbookDefinition: %s" % e.columns
        )

    return wb


@b.session_aware()
def update_workbook(name, values, session=None):
    wb = get_workbook(name)

    wb.update(values.copy())

    return wb


@b.session_aware()
def create_or_update_workbook(name, values, session=None):
    if not _get_db_object_by_name(models.Workbook, name):
        return create_workbook(values)
    else:
        return update_workbook(name, values)


@b.session_aware()
def delete_workbook(name, session=None):
    wb = get_workbook(name)

    session.delete(wb)


@b.session_aware()
def delete_workbooks(**kwargs):
    return _delete_all(models.Workbook, **kwargs)


# Workflow definitions.

def get_workflow_definition(identifier):
    """Gets workflow definition by name or uuid.

    :param identifier: Identifier could be in the format of plain string or
                       uuid.
    :return: Workflow definition.
    """
    wf_def = _get_db_object_by_name_or_id(
        models.WorkflowDefinition,
        identifier
    )

    if not wf_def:
        raise exc.DBEntityNotFoundError(
            "Workflow not found [workflow_identifier=%s]" % identifier
        )

    return wf_def


def get_workflow_definition_by_id(id):
    wf_def = _get_db_object_by_id(models.WorkflowDefinition, id)

    if not wf_def:
        raise exc.DBEntityNotFoundError(
            "Workflow not found [workflow_id=%s]" % id
        )

    return wf_def


def load_workflow_definition(name):
    return _get_db_object_by_name(models.WorkflowDefinition, name)


def get_workflow_definitions(sort_keys=['created_at'], fields=None, **kwargs):
    if fields and 'input' in fields:
        fields.remove('input')
        fields.append('spec')

    return _get_collection_sorted_by_name(
        model=models.WorkflowDefinition,
        sort_keys=sort_keys,
        fields=fields,
        **kwargs
    )


@b.session_aware()
def create_workflow_definition(values, session=None):
    wf_def = models.WorkflowDefinition()

    wf_def.update(values.copy())

    try:
        wf_def.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryError(
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
        # Check cron triggers.
        cron_triggers = get_cron_triggers(insecure=True, workflow_id=wf_def.id)

        for c_t in cron_triggers:
            if c_t.project_id != wf_def.project_id:
                raise exc.NotAllowedException(
                    "Can not update scope of workflow that has cron triggers "
                    "associated in other tenants. [workflow_identifier=%s]" %
                    identifier
                )

        # Check event triggers.
        event_triggers = get_event_triggers(
            insecure=True,
            workflow_id=wf_def.id
        )
        for e_t in event_triggers:
            if e_t.project_id != wf_def.project_id:
                raise exc.NotAllowedException(
                    "Can not update scope of workflow that has event triggers "
                    "associated in other tenants. [workflow_identifier=%s]" %
                    identifier
                )

    wf_def.update(values.copy())

    return wf_def


@b.session_aware()
def create_or_update_workflow_definition(name, values, session=None):
    if not _get_db_object_by_name(models.WorkflowDefinition, name):
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

    cron_triggers = get_cron_triggers(insecure=True, workflow_id=wf_def.id)
    if cron_triggers:
        raise exc.DBError(
            "Can't delete workflow that has cron triggers associated. "
            "[workflow_identifier=%s], [cron_trigger_id(s)=%s]" %
            (identifier, ', '.join([t.id for t in cron_triggers]))
        )

    event_triggers = get_event_triggers(insecure=True, workflow_id=wf_def.id)

    if event_triggers:
        raise exc.DBError(
            "Can't delete workflow that has event triggers associated. "
            "[workflow_identifier=%s], [event_trigger_id(s)=%s]" %
            (identifier, ', '.join([t.id for t in event_triggers]))
        )

    # Delete workflow members first.
    delete_resource_members(resource_type='workflow', resource_id=wf_def.id)

    session.delete(wf_def)


@b.session_aware()
def delete_workflow_definitions(**kwargs):
    return _delete_all(models.WorkflowDefinition, **kwargs)


# Action definitions.

def get_action_definition_by_id(id):
    action_def = _get_db_object_by_id(models.ActionDefinition, id)

    if not action_def:
        raise exc.DBEntityNotFoundError(
            "Action not found [action_id=%s]" % id
        )

    return action_def


def get_action_definition(identifier):
    a_def = _get_db_object_by_name_or_id(
        models.ActionDefinition,
        identifier
    )

    if not a_def:
        raise exc.DBEntityNotFoundError(
            "Action definition not found [action_name=%s]" % identifier
        )

    return a_def


def load_action_definition(name):
    return _get_db_object_by_name(models.ActionDefinition, name)


def get_action_definitions(**kwargs):
    return _get_collection_sorted_by_name(
        model=models.ActionDefinition,
        **kwargs
    )


@b.session_aware()
def create_action_definition(values, session=None):
    a_def = models.ActionDefinition()

    a_def.update(values)

    try:
        a_def.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for action %s: %s" % (a_def.name, e.columns)
        )

    return a_def


@b.session_aware()
def update_action_definition(identifier, values, session=None):
    a_def = get_action_definition(identifier)

    a_def.update(values.copy())

    return a_def


@b.session_aware()
def create_or_update_action_definition(name, values, session=None):
    if not _get_db_object_by_name(models.ActionDefinition, name):
        return create_action_definition(values)
    else:
        return update_action_definition(name, values)


@b.session_aware()
def delete_action_definition(identifier, session=None):
    a_def = get_action_definition(identifier)

    session.delete(a_def)


@b.session_aware()
def delete_action_definitions(**kwargs):
    return _delete_all(models.ActionDefinition, **kwargs)


# Action executions.

def get_action_execution(id):
    a_ex = _get_db_object_by_id(models.ActionExecution, id)

    if not a_ex:
        raise exc.DBEntityNotFoundError(
            "ActionExecution not found [id=%s]" % id
        )

    return a_ex


def load_action_execution(id):
    return _get_db_object_by_id(models.ActionExecution, id)


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
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for ActionExecution: %s" % e.columns
        )

    return a_ex


@b.session_aware()
def update_action_execution(id, values, session=None):
    a_ex = get_action_execution(id)

    a_ex.update(values.copy())

    return a_ex


@b.session_aware()
def create_or_update_action_execution(id, values, session=None):
    if not _get_db_object_by_id(models.ActionExecution, id):
        return create_action_execution(values)
    else:
        return update_action_execution(id, values)


@b.session_aware()
def delete_action_execution(id, session=None):
    a_ex = get_action_execution(id)

    session.delete(a_ex)


@b.session_aware()
def delete_action_executions(**kwargs):
    return _delete_all(models.ActionExecution, **kwargs)


def _get_action_executions(**kwargs):
    return _get_collection_sorted_by_time(models.ActionExecution, **kwargs)


# Workflow executions.

def get_workflow_execution(id):
    wf_ex = _get_db_object_by_id(models.WorkflowExecution, id)

    if not wf_ex:
        raise exc.DBEntityNotFoundError(
            "WorkflowExecution not found [id=%s]" % id
        )

    return wf_ex


def load_workflow_execution(id):
    return _get_db_object_by_id(models.WorkflowExecution, id)


def ensure_workflow_execution_exists(id):
    get_workflow_execution(id)


def get_workflow_executions(**kwargs):
    return _get_collection_sorted_by_time(
        models.WorkflowExecution,
        **kwargs
    )


@b.session_aware()
def create_workflow_execution(values, session=None):
    wf_ex = models.WorkflowExecution()

    wf_ex.update(values.copy())

    try:
        wf_ex.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for WorkflowExecution: %s" % e.columns
        )

    return wf_ex


@b.session_aware()
def update_workflow_execution(id, values, session=None):
    wf_ex = get_workflow_execution(id)

    wf_ex.update(values.copy())

    return wf_ex


@b.session_aware()
def create_or_update_workflow_execution(id, values, session=None):
    if not _get_db_object_by_id(models.WorkflowExecution, id):
        return create_workflow_execution(values)
    else:
        return update_workflow_execution(id, values)


@b.session_aware()
def delete_workflow_execution(id, session=None):
    wf_ex = get_workflow_execution(id)

    session.delete(wf_ex)


@b.session_aware()
def delete_workflow_executions(**kwargs):
    return _delete_all(models.WorkflowExecution, **kwargs)


# Tasks executions.

def get_task_execution(id):
    task_ex = _get_db_object_by_id(models.TaskExecution, id)

    if not task_ex:
        raise exc.DBEntityNotFoundError(
            "Task execution not found [id=%s]" % id
        )

    return task_ex


def load_task_execution(id):
    return _get_db_object_by_id(models.TaskExecution, id)


def get_task_executions(**kwargs):
    return _get_task_executions(**kwargs)


def _get_incomplete_task_executions_query(kwargs):
    query = b.model_query(models.TaskExecution)

    query = query.filter_by(**kwargs)

    query = query.filter(
        sa.or_(
            models.TaskExecution.state == 'IDLE',
            models.TaskExecution.state == 'RUNNING',
            models.TaskExecution.state == 'WAITING',
            models.TaskExecution.state == 'DELAYED'
        )
    )

    return query


def get_incomplete_task_executions(**kwargs):
    query = _get_incomplete_task_executions_query(kwargs)

    return query.all()


def get_incomplete_task_executions_count(**kwargs):
    query = _get_incomplete_task_executions_query(kwargs)

    return query.count()


@b.session_aware()
def create_task_execution(values, session=None):
    task_ex = models.TaskExecution()

    task_ex.update(values)

    try:
        task_ex.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for TaskExecution: %s" % e.columns
        )

    return task_ex


@b.session_aware()
def update_task_execution(id, values, session=None):
    task_ex = get_task_execution(id)

    task_ex.update(values.copy())

    return task_ex


@b.session_aware()
def create_or_update_task_execution(id, values, session=None):
    if not _get_db_object_by_id(models.TaskExecution, id):
        return create_task_execution(values)
    else:
        return update_task_execution(id, values)


@b.session_aware()
def delete_task_execution(id, session=None):
    task_ex = get_task_execution(id)

    session.delete(task_ex)


@b.session_aware()
def delete_task_executions(**kwargs):
    return _delete_all(models.TaskExecution, **kwargs)


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
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for DelayedCall: %s" % e.columns
        )

    return delayed_call


@b.session_aware()
def delete_delayed_call(id, session=None):
    delayed_call = get_delayed_call(id)

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
    delayed_call = _get_db_object_by_id(models.DelayedCall, id)

    if not delayed_call:
        raise exc.DBEntityNotFoundError(
            "Delayed Call not found [id=%s]" % id
        )

    return delayed_call


def get_delayed_calls(**kwargs):
    return _get_collection(
        model=models.DelayedCall,
        **kwargs
    )


@b.session_aware()
def delete_delayed_calls(**kwargs):
    return _delete_all(models.DelayedCall, **kwargs)


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
            models.WorkflowExecution.state == "ERROR",
            models.WorkflowExecution.state == "CANCELLED"
        )
    )

    return query.all()


# Cron triggers.

def get_cron_trigger(name):
    cron_trigger = _get_db_object_by_name(models.CronTrigger, name)

    if not cron_trigger:
        raise exc.DBEntityNotFoundError(
            "Cron trigger not found [name=%s]" % name
        )

    return cron_trigger


def load_cron_trigger(name):
    return _get_db_object_by_name(models.CronTrigger, name)


def get_cron_triggers(insecure=False, **kwargs):
    return _get_collection_sorted_by_name(
        models.CronTrigger,
        insecure=insecure,
        **kwargs
    )


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
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for cron trigger %s: %s"
            % (cron_trigger.name, e.columns)
        )
    # TODO(nmakhotkin): Remove this 'except' after fixing
    # https://bugs.launchpad.net/oslo.db/+bug/1458583.
    except db_exc.DBError as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for cron trigger: %s" % e
        )

    return cron_trigger


@b.session_aware()
def update_cron_trigger(name, values, session=None, query_filter=None):
    cron_trigger = get_cron_trigger(name)

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
    cron_trigger = _get_db_object_by_name(models.CronTrigger, name)

    if not cron_trigger:
        return create_cron_trigger(values)
    else:
        updated, _ = update_cron_trigger(name, values)
        return updated


@b.session_aware()
def delete_cron_trigger(name, session=None):
    cron_trigger = get_cron_trigger(name)

    # Delete the cron trigger by ID and get the affected row count.
    table = models.CronTrigger.__table__
    result = session.execute(
        table.delete().where(table.c.id == cron_trigger.id)
    )

    return result.rowcount


@b.session_aware()
def delete_cron_triggers(**kwargs):
    return _delete_all(models.CronTrigger, **kwargs)


# Environments.

def get_environment(name):
    env = _get_db_object_by_name(models.Environment, name)

    if not env:
        raise exc.DBEntityNotFoundError(
            "Environment not found [name=%s]" % name
        )

    return env


def load_environment(name):
    return _get_db_object_by_name(models.Environment, name)


def get_environments(**kwargs):
    return _get_collection_sorted_by_name(models.Environment, **kwargs)


@b.session_aware()
def create_environment(values, session=None):
    env = models.Environment()

    env.update(values)

    try:
        env.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for Environment: %s" % e.columns
        )

    return env


@b.session_aware()
def update_environment(name, values, session=None):
    env = get_environment(name)

    env.update(values)

    return env


@b.session_aware()
def create_or_update_environment(name, values, session=None):
    env = _get_db_object_by_name(models.Environment, name)

    if not env:
        return create_environment(values)
    else:
        return update_environment(name, values)


@b.session_aware()
def delete_environment(name, session=None):
    env = get_environment(name)

    session.delete(env)


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
        raise exc.DBDuplicateEntryError(
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
        raise exc.DBEntityNotFoundError(
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
        raise exc.DBEntityNotFoundError(
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
        raise exc.DBEntityNotFoundError(
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
        raise exc.DBEntityNotFoundError(
            "Resource member not found [resource_id=%s, member_id=%s]" %
            (resource_id, member_id)
        )

    # TODO(kong): Check association with cron triggers when deleting a workflow
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


# Event triggers.

def get_event_trigger(id, insecure=False):
    event_trigger = _get_event_trigger(id, insecure)

    if not event_trigger:
        raise exc.DBEntityNotFoundError(
            "Event trigger not found [id=%s]." % id
        )

    return event_trigger


def get_event_triggers(insecure=False, **kwargs):
    return _get_collection_sorted_by_time(
        model=models.EventTrigger,
        insecure=insecure,
        **kwargs
    )


@b.session_aware()
def create_event_trigger(values, session=None):
    event_trigger = models.EventTrigger()

    event_trigger.update(values)

    try:
        event_trigger.save(session=session)
    except db_exc.DBDuplicateEntry as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for event trigger %s: %s"
            % (event_trigger.id, e.columns)
        )
    # TODO(nmakhotkin): Remove this 'except' after fixing
    # https://bugs.launchpad.net/oslo.db/+bug/1458583.
    except db_exc.DBError as e:
        raise exc.DBDuplicateEntryError(
            "Duplicate entry for event trigger: %s" % e
        )

    return event_trigger


@b.session_aware()
def update_event_trigger(id, values, session=None):
    event_trigger = get_event_trigger(id)

    event_trigger.update(values.copy())

    return event_trigger


@b.session_aware()
def delete_event_trigger(id, session=None):
    event_trigger = get_event_trigger(id)

    session.delete(event_trigger)


@b.session_aware()
def delete_event_triggers(**kwargs):
    return _delete_all(models.EventTrigger, **kwargs)


def _get_event_trigger(id, insecure=False):
    if insecure:
        return b.model_query(models.EventTrigger).filter_by(id=id).first()
    else:
        return _get_db_object_by_id(models.EventTrigger, id)


def ensure_event_trigger_exists(id):
    get_event_trigger(id)


# Locks.

@b.session_aware()
def create_named_lock(name, session=None):
    # This method has to work without SQLAlchemy session because
    # session may not immediately issue an SQL query to a database
    # and instead just schedule it whereas we need to make sure to
    # issue a query immediately.
    session.flush()

    insert = models.NamedLock.__table__.insert()

    lock_id = utils.generate_unicode_uuid()

    session.execute(insert.values(id=lock_id, name=name))

    session.flush()

    return lock_id


def get_named_locks(**kwargs):
    return _get_collection(models.NamedLock, **kwargs)


@b.session_aware()
def delete_named_lock(lock_id, session=None):
    # This method has to work without SQLAlchemy session because
    # session may not immediately issue an SQL query to a database
    # and instead just schedule it whereas we need to make sure to
    # issue a query immediately.
    session.flush()

    table = models.NamedLock.__table__

    delete = table.delete()

    session.execute(delete.where(table.c.id == lock_id))

    session.flush()


@contextlib.contextmanager
def named_lock(name):
    lock_id = None
    try:
        lock_id = create_named_lock(name)
        yield
    finally:
        delete_named_lock(lock_id)
