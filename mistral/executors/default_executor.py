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

from mistral_lib import actions as mistral_lib
from oslo_log import log as logging
from osprofiler import profiler

from mistral import context
from mistral import exceptions as exc
from mistral.executors import base
from mistral.rpc import clients as rpc
from mistral.services import action_heartbeat_sender
from mistral.utils import ThreadWithException

LOG = logging.getLogger(__name__)


class DefaultExecutor(base.Executor):
    def __init__(self):
        self._engine_client = rpc.get_engine_client()

    @profiler.trace('default-executor-run-action', hide_args=True)
    def run_action(self, action, action_ex_id, safe_rerun, exec_ctx,
                   redelivered=False, target=None, async_=True, timeout=None):
        """Runs action.

        :param action: Action to run.
        :param action_ex_id: Action execution id.
        :param safe_rerun: Tells if given action can be safely rerun.
        :param exec_ctx: A dict of values providing information about
            the current execution.
        :param redelivered: Tells if given action was run before on another
            executor.
        :param target: Target (group of action executors).
        :param async_: If True, run action in asynchronous mode (w/o waiting
            for completion).
        :param timeout: a period of time in seconds after which execution of
            action will be interrupted
        :return: Action result.
        """

        try:
            action_heartbeat_sender.add_action(action_ex_id)

            return self._do_run_action(
                action,
                action_ex_id,
                exec_ctx,
                redelivered,
                safe_rerun,
                timeout
            )
        finally:
            action_heartbeat_sender.remove_action(action_ex_id)

    def _do_run_action(self, action, action_ex_id, exec_ctx,
                       redelivered, safe_rerun,
                       timeout):
        def send_error_back(error_msg):
            error_result = mistral_lib.Result(error=error_msg)

            if action_ex_id:
                self._engine_client.on_action_complete(
                    action_ex_id,
                    error_result
                )

                return None

            return error_result

        def _thread_run_action(fn, auth_ctx, action_ctx, result):
            # Run an action in a thread and keep track of the result
            # As we are running in a different thread, we need to set
            # our auth_context correctly
            context.set_ctx(auth_ctx)
            result['r'] = fn(action_ctx)

        if redelivered and not safe_rerun:
            msg = (
                "Request to run an action was redelivered, but it cannot "
                "be re-run safely. The only safe thing to do is fail "
                "it [action=%s]." % action
            )

            return send_error_back(msg)

        # Run action.
        try:
            # NOTE(d0ugal): If the action is a subclass of mistral-lib we
            # know that it expects to be passed an ActionContext.
            if isinstance(action, mistral_lib.Action):
                action_ctx = context.create_action_context(exec_ctx)
            else:
                action_ctx = None
            # NOTE(amorin) we need a dict type to store the result so python
            # will give pointer to this object and not copy the value into a
            # new memory space
            result_ptr = {}
            thread = ThreadWithException(
                target=_thread_run_action,
                args=[action.run, context.ctx(), action_ctx, result_ptr]
            )
            thread.start()
            thread.join(timeout=timeout)
            # Get back result
            result = result_ptr.get('r')

            if thread.is_alive():
                # The action is taking too long.
                # There is no proper way to kill a thread, so we have two
                # options:
                # - Leave the thread alone without taking care
                # - Wait for it to finish now (thread.join())
                # amorin: I decided to wait for the thread to finish, it's a
                # safer decision as we are giving "result" to our thread
                # and we dont want another thread to overwrite this later
                # if we don't wait
                # We may block this mistral thread for an infinite time,
                # but, it's the safest option I came to for now.
                # Note: we were using eventlet here before, and eventlet
                # allowed us to kill the greenthread
                # Let's print a log message about this, so at least, we can
                # identify that we are stuck from logs
                LOG.warning("The action %s timed out, we are now waiting for "
                            "the action thread to finish...", (action_ex_id))
                thread.join()
                raise Exception("Timeout after %s seconds" % (timeout))

            # Note: it's made for backwards compatibility with already
            # existing Mistral actions which don't return result as
            # instance of workflow.utils.Result.
            if not isinstance(result, mistral_lib.Result):
                result = mistral_lib.Result(data=result)

        except BaseException as e:
            msg = (
                "The action raised an exception [action=%s, action_ex_id=%s, "
                "msg='%s']" % (action, action_ex_id, e)
            )
            LOG.warning(msg, exc_info=True)
            return send_error_back(msg)

        # Send action result.
        try:
            if action_ex_id and (action.is_sync() or result.is_error()):
                self._engine_client.on_action_complete(
                    action_ex_id,
                    result,
                    async_=True
                )

        except exc.MistralException as e:
            # In case of a Mistral exception we can try to send error info to
            # engine because most likely it's not related to the infrastructure
            # such as message bus or network. One known case is when the action
            # returns a bad result (e.g. invalid unicode) which can't be
            # serialized.
            msg = (
                "Failed to complete action due to a Mistral exception "
                "[action=%s, action_ex_id=%s]\n %s" %
                (action, action_ex_id, e)
            )

            LOG.exception(msg)

            return send_error_back(msg)
        except Exception as e:
            # If it's not a Mistral exception all we can do is only
            # log the error.
            msg = (
                "Failed to complete action due to an unexpected exception "
                "[action=%s, action_ex_id=%s]\n %s" %
                (action, action_ex_id, e)
            )

            LOG.exception(msg)

        return result
