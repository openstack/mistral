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

from oslo_log import log as logging
from osprofiler import profiler

from mistral.actions import action_factory as a_f
from mistral.engine import base
from mistral.engine.rpc_backend import rpc
from mistral import exceptions as exc
from mistral.utils import inspect_utils as i_u
from mistral.workflow import utils as wf_utils


LOG = logging.getLogger(__name__)


class DefaultExecutor(base.Executor):
    def __init__(self):
        self._engine_client = rpc.get_engine_client()

    @profiler.trace('executor-run-action', hide_args=True)
    def run_action(self, action_ex_id, action_class_str, attributes,
                   action_params, safe_rerun, redelivered=False):
        """Runs action.

        :param action_ex_id: Action execution id.
        :param action_class_str: Path to action class in dot notation.
        :param attributes: Attributes of action class which will be set to.
        :param action_params: Action parameters.
        :param safe_rerun: Tells if given action can be safely rerun.
        :param redelivered: Tells if given action was run before on another
            executor.
        """

        def send_error_back(error_msg):
            error_result = wf_utils.Result(error=error_msg)

            if action_ex_id:
                self._engine_client.on_action_complete(
                    action_ex_id,
                    error_result
                )

                return None

            return error_result

        if redelivered and not safe_rerun:
            msg = (
                "Request to run action %s was redelivered, but action %s"
                " cannot be re-run safely. The only safe thing to do is fail"
                " action."
                % (action_class_str, action_class_str)
            )

            return send_error_back(msg)

        action_cls = a_f.construct_action_class(action_class_str, attributes)

        # Instantiate action.

        try:
            action = action_cls(**action_params)
        except Exception as e:
            msg = ("Failed to initialize action %s. Action init params = %s."
                   " Actual init params = %s. More info: %s"
                   % (action_class_str, i_u.get_arg_list(action_cls.__init__),
                      action_params.keys(), e))
            LOG.warning(msg)

            return send_error_back(msg)

        # Run action.

        try:
            result = action.run()

            # Note: it's made for backwards compatibility with already
            # existing Mistral actions which don't return result as
            # instance of workflow.utils.Result.
            if not isinstance(result, wf_utils.Result):
                result = wf_utils.Result(data=result)

        except Exception as e:
            msg = ("Failed to run action [action_ex_id=%s, action_cls='%s',"
                   " attributes='%s', params='%s']\n %s"
                   % (action_ex_id, action_cls, attributes, action_params, e))
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
            msg = ("Failed to call engine's on_action_complete() method due"
                   " to a Mistral exception"
                   " [action_ex_id=%s, action_cls='%s',"
                   " attributes='%s', params='%s']\n %s"
                   % (action_ex_id, action_cls, attributes, action_params, e))
            LOG.exception(msg)

            return send_error_back(msg)
        except Exception as e:
            # If it's not a Mistral exception all we can do is only
            # log the error.
            msg = ("Failed to call engine's on_action_complete() method due"
                   " to an unexpected exception"
                   " [action_ex_id=%s, action_cls='%s',"
                   " attributes='%s', params='%s']\n %s"
                   % (action_ex_id, action_cls, attributes, action_params, e))
            LOG.exception(msg)

        return result
