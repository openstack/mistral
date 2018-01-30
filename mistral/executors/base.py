# Copyright 2017 - Brocade Communications Systems, Inc.
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

import abc
import six

from mistral import serialization
from mistral_lib.actions import types
from stevedore import driver

_EXECUTORS = {}
serialization.register_serializer(types.Result, types.ResultSerializer())


def cleanup():
    global _EXECUTORS
    _EXECUTORS = {}


def get_executor(exec_type):
    global _EXECUTORS

    if not _EXECUTORS.get(exec_type):
        mgr = driver.DriverManager(
            'mistral.executors',
            exec_type,
            invoke_on_load=True
        )

        _EXECUTORS[exec_type] = mgr.driver

    return _EXECUTORS[exec_type]


@six.add_metaclass(abc.ABCMeta)
class Executor(object):
    """Action executor interface."""

    @abc.abstractmethod
    def run_action(self, action_ex_id, action_cls_str, action_cls_attrs,
                   params, safe_rerun, execution_context, redelivered=False,
                   target=None, async_=True, timeout=None):
        """Runs action.

        :param timeout: a period of time in seconds after which execution of
            action will be interrupted
        :param action_ex_id: Corresponding action execution id.
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
        :return: Action result.
        """
        raise NotImplementedError()
