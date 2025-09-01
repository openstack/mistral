# Copyright 2013 - Mirantis, Inc.
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

import cachetools

from oslo_config import cfg
from oslo_db import options
from oslo_db.sqlalchemy import enginefacade
import osprofiler.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.sql import column

from mistral.db.sqlalchemy import sqlite_lock
from mistral import exceptions as exc
from mistral_lib import utils

import threading


# Note(dzimine): sqlite only works for basic testing.
options.set_defaults(cfg.CONF, connection="sqlite:///mistral.sqlite")

_DB_SESSION_THREAD_LOCAL_NAME = "__db_sql_alchemy_session__"
_TX_SCOPED_CACHE_THREAD_LOCAL_NAME = "__tx_scoped_cache__"

_facade = None
_sqlalchemy_create_engine_orig = sa.create_engine

# NOTE(amorin) Create a reentrant lock so only one thread can create a SQL
# session at a time.
# Without the lock, after evenlet-removal, multiple threads could create
# session at the same time (e.g. one thread start a session, start working in
# that session, another could start a session in the meantime).
# When multiple threads try to start sessions at the same time, some sql
# backend could fail with errors like: cannot start a transaction within a
# transaction (sqlite for e.g.), because threads were re-using the same
# connection to create another session (and sqlite does not like that).
# So to avoid this, when a thread create a session, it will grab that lock
# until it has finished.
# The lock is used a two places: one here (in base.py) in session_aware
# decorator, and another one (in db/v2/sqlalchemy/api.py) for def transaction
# context manager.
tx_lock = threading.RLock()


def _get_facade():
    global _facade

    if not _facade:
        ctx = enginefacade.transaction_context()
        ctx.configure(sqlite_fk=True)
        _facade = ctx.writer

        if cfg.CONF.profiler.enabled:
            if cfg.CONF.profiler.trace_sqlalchemy:
                osprofiler.sqlalchemy.add_tracing(
                    sa,
                    _facade.get_engine(),
                    'db'
                )

    return _facade


# Monkey-patching sqlalchemy to set the isolation_level
# as this configuration is not exposed by oslo_db.
def _sqlalchemy_create_engine_wrapper(*args, **kwargs):
    # sqlite (used for unit testing and not allowed for production)
    # does not support READ_COMMITTED.
    # Checking the drivername using the args and not the get_driver_name()
    # method because that method requires a session.
    if args[0].drivername != 'sqlite':
        kwargs["isolation_level"] = "READ_COMMITTED"

    return _sqlalchemy_create_engine_orig(*args, **kwargs)


def get_engine():
    # If the patch was not applied yet.
    if sa.create_engine != _sqlalchemy_create_engine_wrapper:
        # Replace the original create_engine with our wrapper.
        sa.create_engine = _sqlalchemy_create_engine_wrapper

    return _get_facade().get_engine()


def _get_session():
    sessionmaker = _get_facade().get_sessionmaker()
    return sessionmaker()


def _get_thread_local_session():
    return utils.get_thread_local(_DB_SESSION_THREAD_LOCAL_NAME)


def get_tx_scoped_cache():
    return utils.get_thread_local(_TX_SCOPED_CACHE_THREAD_LOCAL_NAME)


def _get_or_create_thread_local_session():
    ses = _get_thread_local_session()

    if ses:
        return ses, False

    ses = _get_session()
    _set_thread_local_session(ses)

    return ses, True


def _set_thread_local_session(session):
    utils.set_thread_local(_DB_SESSION_THREAD_LOCAL_NAME, session)

    if session is not None:
        utils.set_thread_local(
            _TX_SCOPED_CACHE_THREAD_LOCAL_NAME,
            cachetools.LRUCache(maxsize=1000)
        )
    else:
        utils.set_thread_local(_TX_SCOPED_CACHE_THREAD_LOCAL_NAME, None)


def session_aware(param_name="session"):
    """Decorator for methods working within db session."""

    def _decorator(func):
        def _within_session(*args, **kw):
            with tx_lock:
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
    """Starts transaction.

    Opens new database session and starts new transaction assuming
    there wasn't any opened sessions within the same thread.
    """
    if _get_thread_local_session():
        raise exc.DataAccessException(
            "Database transaction has already been started."
        )

    _set_thread_local_session(_get_session())


def release_locks_if_sqlite(session):
    if get_driver_name() == 'sqlite':
        sqlite_lock.release_locks(session)


def commit_tx():
    """Commits previously started database transaction."""
    ses = _get_thread_local_session()

    if not ses:
        raise exc.DataAccessException(
            "Nothing to commit. Database transaction"
            " has not been previously started."
        )

    ses.commit()


def rollback_tx():
    """Rolls back previously started database transaction."""
    ses = _get_thread_local_session()

    if not ses:
        raise exc.DataAccessException(
            "Nothing to roll back. Database transaction has not been started."
        )

    ses.rollback()


def end_tx():
    """Ends transaction.

    Ends current database transaction.
    It rolls back all uncommitted changes and closes database session.
    """
    ses = _get_thread_local_session()

    if not ses:
        raise exc.DataAccessException(
            "Database transaction has not been started."
        )

    if ses.dirty:
        rollback_tx()

    release_locks_if_sqlite(ses)

    ses.close()
    _set_thread_local_session(None)


@session_aware()
def get_driver_name(session=None):
    return session.bind.url.drivername


@session_aware()
def get_dialect_name(session=None):
    return session.bind.url.get_dialect().name


@session_aware()
def model_query(model, columns=(), session=None):
    """Query helper.

    :param model: Base model to query.
    :param columns: Optional. Which columns to be queried.
    """

    if columns:
        _columns = (column(c) if isinstance(c, str) else c for c in columns)
        return session.query(*_columns)

    return session.query(model)
