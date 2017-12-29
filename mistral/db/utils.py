# Copyright 2016 - Nokia Networks
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

import functools

from oslo_db import exception as db_exc
from oslo_log import log as logging
import tenacity

from mistral import context
from mistral import exceptions as exc
from mistral.services import security


LOG = logging.getLogger(__name__)

_RETRY_ERRORS = (db_exc.DBDeadlock, db_exc.DBConnectionError)


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(_RETRY_ERRORS),
    stop=tenacity.stop_after_attempt(50),
    wait=tenacity.wait_incrementing(start=0, increment=0.1, max=2)
)
def _with_auth_context(auth_ctx, func, *args, **kw):
    """Runs the given function with the specified auth context.

    :param auth_ctx: Authentication context.
    :param func: Function to run with the specified auth context.
    :param args: Function positional arguments.
    :param kw: Function keyword arguments.
    :return: Function result.
    """
    old_auth_ctx = context.ctx() if context.has_ctx() else None

    context.set_ctx(auth_ctx)

    try:
        return func(*args, **kw)
    except _RETRY_ERRORS:
        LOG.exception(
            "DB error detected, operation will be retried: %s", func
        )

        raise
    finally:
        context.set_ctx(old_auth_ctx)


def retry_on_db_error(func):
    """Decorates the given function so that it retries on DB errors.

    Note that the decorator retries the function/method only on some
    of the DB errors that are considered to be worth retrying, like
    deadlocks and disconnections.

    :param func: Function to decorate.
    :return: Decorated function.
    """
    @functools.wraps(func)
    def decorate(*args, **kw):
        # Retrying library decorator might potentially run a decorated
        # function within a new thread so it's safer not to apply the
        # decorator directly to a target method/function because we can
        # lose an authentication context.
        # The solution is to create one more function and explicitly set
        # auth context before calling it (potentially in a new thread).
        auth_ctx = context.ctx() if context.has_ctx() else None

        return _with_auth_context(auth_ctx, func, *args, **kw)

    return decorate


def check_db_obj_access(db_obj):
    """Check accessibility to db object."""
    ctx = context.ctx()
    is_admin = ctx.is_admin

    if not is_admin and db_obj.project_id != security.get_project_id():
        raise exc.NotAllowedException(
            "Can not access %s resource of other projects, ID: %s" %
            (db_obj.__class__.__name__, db_obj.id)
        )

    if not is_admin and hasattr(db_obj, 'is_system') and db_obj.is_system:
        raise exc.InvalidActionException(
            "Can not modify a system %s resource, ID: %s" %
            (db_obj.__class__.__name__, db_obj.id)
        )
