# Copyright 2015 - Alcatel-lucent, Inc.
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

import datetime
import traceback

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import periodic_task
from oslo_service import threadgroup

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api

LOG = logging.getLogger(__name__)

CONF = cfg.CONF


class ExecutionExpirationPolicy(periodic_task.PeriodicTasks):
    """Expiration Policy task.

    This task will run every 'evaluation_interval' and will remove old
    executions (expired execution). The time interval is configurable
    In the 'mistral.cfg' and also the expiration time (both in minutes).
    By default the interval set to 'None' so this task will be disabled.
    """

    def __init__(self, conf):
        super(ExecutionExpirationPolicy, self).__init__(conf)

        interval = CONF.execution_expiration_policy.evaluation_interval
        older_than = CONF.execution_expiration_policy.older_than

        if (interval and older_than and older_than >= 1):
            _periodic_task = periodic_task.periodic_task(
                spacing=interval * 60,
                run_immediately=True

            )
            self.add_periodic_task(
                _periodic_task(run_execution_expiration_policy)
            )
        else:
            LOG.debug("Expiration policy disabled. Evaluation_interval "
                      "is not configured or older_than < '1'.")


def _delete_expired_executions(batch_size, expired_time):
    if batch_size:
        while True:
            with db_api.transaction():
                # TODO(gpaz): In the future should use generic method with
                # filters params and not specific method that filter by time.
                expired_executions = db_api.get_expired_executions(
                    expired_time,
                    limit=batch_size
                )

                if not expired_executions:
                    break
                _delete(expired_executions)
    else:
        with db_api.transaction():
            expired_executions = db_api.get_expired_executions(expired_time)
            _delete(expired_executions)


def _delete(exp_executions):
    for execution in exp_executions:
        try:
            # Setup project_id for _secure_query delete execution.
            # TODO(tuan_luong): Manipulation with auth_ctx should be
            # out of db transaction scope.
            ctx = auth_ctx.MistralContext(
                user_id=None,
                project_id=execution.project_id,
                auth_token=None,
                is_admin=True
            )
            auth_ctx.set_ctx(ctx)

            LOG.debug(
                'DELETE execution id : %s from date : %s '
                'according to expiration policy',
                execution.id,
                execution.updated_at
            )
            db_api.delete_workflow_execution(execution.id)
        except Exception as e:
            msg = ("Failed to delete [execution_id=%s]\n %s"
                   % (execution.id, traceback.format_exc(e)))
            LOG.warning(msg)
        finally:
            auth_ctx.set_ctx(None)


def run_execution_expiration_policy(self, ctx):
    LOG.debug("Starting expiration policy.")

    older_than = CONF.execution_expiration_policy.older_than
    exp_time = (datetime.datetime.now()
                - datetime.timedelta(minutes=older_than))

    batch_size = CONF.execution_expiration_policy.batch_size

    # The default value of batch size is 0
    # If it is not set, size of batch will be the size
    # of total number of expired executions.
    _delete_expired_executions(batch_size, exp_time)


def setup():
    tg = threadgroup.ThreadGroup()
    pt = ExecutionExpirationPolicy(CONF)

    ctx = auth_ctx.MistralContext(
        user_id=None,
        project_id=None,
        auth_token=None,
        is_admin=True
    )

    tg.add_dynamic_timer(
        pt.run_periodic_tasks,
        initial_delay=None,
        periodic_interval_max=1,
        context=ctx
    )

    return tg
