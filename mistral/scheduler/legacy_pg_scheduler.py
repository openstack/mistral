# Copyright 2021 - NetCracker, Inc.
# Modified in 2025 by NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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

from oslo_log import log as logging

from mistral import context
from mistral.db import utils as db_utils
from mistral.db.v2 import api as db_api
from mistral.engine import post_tx_queue
from mistral.scheduler import legacy_scheduler
from mistral_lib import utils


LOG = logging.getLogger(__name__)


class LegacyPGScheduler(legacy_scheduler.LegacyScheduler):

    def has_scheduled_jobs(self, **filters):
        return db_api.get_delayed_calls_count(**filters) > 0

    def _process_delayed_calls(self, ctx=None):
        """Run delayed required calls.

        This algorithm should work with transactions having at least
        'READ-COMMITTED' isolation mode.

        :param ctx: Auth context.
        """

        for _ in range(self._batch_size):
            self._process_single_delayed_call(ctx)

        context.set_ctx(None)

    @post_tx_queue.run
    def _process_single_delayed_call(self, ctx=None):
        # Select and capture calls matching time criteria.
        with db_api.transaction():
            db_call = self._capture_calls(1)

            if not db_call:
                return

            # Determine target methods, deserialize arguments etc.
            prepared_call = self._prepare_calls(db_call)

            # Invoke prepared calls.
            self._invoke_calls(prepared_call)

            # Delete invoked calls from DB.
            self.delete_calls(db_call)

    @staticmethod
    @db_utils.retry_on_db_error
    def _capture_calls(batch_size):
        """Captures delayed calls eligible for processing (based on time).

        The intention of this method is to select delayed calls based on time
        criteria and mark them in DB as being processed so that no other
        threads could process them in parallel.

        :return: A list of delayed calls captured for further processing.
        """

        time_filter = utils.utc_now_sec() + datetime.timedelta(seconds=1)

        result = db_api.get_unlocked_delayed_calls_to_start(
            time_filter,
            batch_size
        )

        LOG.debug("Scheduler captured %s delayed calls.", len(result))

        return result

    @staticmethod
    def _invoke_calls(delayed_calls):
        """Invokes prepared delayed calls.

        :param delayed_calls: Prepared delayed calls represented as tuples
        (target_auth_context, target_method, method_args).
        """

        ctx_serializer = context.RpcContextSerializer()

        for (target_auth_context, target_method, method_args) in delayed_calls:
            try:
                # Set the correct context for the method.
                ctx_serializer.deserialize_context(target_auth_context)

                # Add flag to skip new transaction
                method_args["skip_tx"] = True

                # Invoke the method.
                target_method(**method_args)
            except Exception as e:
                LOG.exception(
                    "Delayed call failed, method: %s, exception: %s",
                    target_method,
                    e
                )
