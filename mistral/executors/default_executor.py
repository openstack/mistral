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

from eventlet import timeout as ev_timeout
from mistral_lib import actions as mistral_lib
from oslo_log import log as logging
from osprofiler import profiler

from mistral.actions import action_factory as a_f
from mistral import context
from mistral import exceptions as exc
from mistral.executors import base
from mistral.rpc import clients as rpc
from mistral.utils import inspect_utils as i_u


LOG = logging.getLogger(__name__)


class DefaultExecutor(base.Executor):
    def __init__(self):
        self._engine_client = rpc.get_engine_client()

    @profiler.trace('default-executor-run-action', hide_args=True)
    def run_action(self, action_ex_id, action_cls_str, action_cls_attrs,
                   params, safe_rerun, execution_context, redelivered=False,
                   target=None, async_=True, timeout=None):
        """Runs action.

        :param action_ex_id: Action execution id.
        :param action_cls_str: Path to action class in dot notation.
        :param action_cls_attrs: Attributes of action class which
            will be set to.
        :param params: Action parameters.
        :param safe_rerun: Tells if given action can be safely rerun.
        :param execution_context: A dict of values providing information about
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

        def send_error_back(error_msg):
            error_result = mistral_lib.Result(error=error_msg)

            if action_ex_id:
                self._engine_client.on_action_complete(
                    action_ex_id,
                    error_result
                )

                return None

            return error_result

        if redelivered and not safe_rerun:
            msg = (
                "Request to run action %s was redelivered, but action %s "
                "cannot be re-run safely. The only safe thing to do is fail "
                "action." % (action_cls_str, action_cls_str)
            )

            return send_error_back(msg)

        # Load action module.
        action_cls = a_f.construct_action_class(
            action_cls_str,
            action_cls_attrs
        )

        # Instantiate action.
        try:
            action = action_cls(**params)
        except Exception as e:
            msg = (
                "Failed to initialize action %s. Action init params = %s. "
                "Actual init params = %s. More info: %s" % (
                    action_cls_str,
                    i_u.get_arg_list(action_cls.__init__),
                    params.keys(),
                    e
                )
            )

            LOG.warning(msg)

            return send_error_back(msg)

        # Run action.
        try:
            with ev_timeout.Timeout(seconds=timeout):
                # NOTE(d0ugal): If the action is a subclass of mistral-lib we
                # know that it expects to be passed the context.
                if isinstance(action, mistral_lib.Action):
                    action_ctx = context.create_action_context(
                        execution_context)
                    result = action.run(action_ctx)
                else:
                    result = action.run()

            # Note: it's made for backwards compatibility with already
            # existing Mistral actions which don't return result as
            # instance of workflow.utils.Result.
            if not isinstance(result, mistral_lib.Result):
                result = mistral_lib.Result(data=result)

        except BaseException as e:
            msg = (
                "Failed to run action [action_ex_id=%s, action_cls='%s', "
                "attributes='%s', params='%s']\n %s" % (
                    action_ex_id,
                    action_cls,
                    action_cls_attrs,
                    params,
                    e
                )
            )

            LOG.exception(msg)

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
                "[action_ex_id=%s, action_cls='%s', "
                "attributes='%s', params='%s']\n %s" % (
                    action_ex_id,
                    action_cls,
                    action_cls_attrs,
                    params,
                    e
                )
            )

            LOG.exception(msg)

            return send_error_back(msg)
        except Exception as e:
            # If it's not a Mistral exception all we can do is only
            # log the error.
            msg = (
                "Failed to complete action due to an unexpected exception "
                "[action_ex_id=%s, action_cls='%s', "
                "attributes='%s', params='%s']\n %s" % (
                    action_ex_id,
                    action_cls,
                    action_cls_attrs,
                    params,
                    e
                )
            )

            LOG.exception(msg)

        return result
