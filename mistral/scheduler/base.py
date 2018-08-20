# Copyright 2018 - Nokia Networks.
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

import abc
import six


@six.add_metaclass(abc.ABCMeta)
class Scheduler(object):
    """Scheduler interface.

    Responsible for scheduling jobs to be executed at some point in future.
    """

    @abc.abstractmethod
    def schedule(self, job, allow_redistribute=False):
        """Schedules a delayed call to be invoked at some point in future.

        :param job: Scheduler Job. An instance of :class:`SchedulerJob`.
        :param allow_redistribute: If True then the method is allowed to
            reroute the call to other Scheduler instances available in the
            cluster.
        """
        raise NotImplementedError


class SchedulerJob(object):
    """Scheduler job.

    Encapsulates information about a command that needs to be executed
    at some point in future.
    """
    def __init__(self, run_after=0, target_factory_func_name=None,
                 func_name=None, func_args=None,
                 func_arg_serializers=None):
        """Initializes a Scheduler Job.

        :param run_after: Amount of seconds after which to invoke
            a scheduled call.
        :param target_factory_func_name: Full path of a function that returns
            a target object against which a method specified with the
            "func_name" should be invoked. Optional. If None, then "func_name"
            must be a full path of a static function to invoke.
        :param func_name: Function or method name to invoke when a job gets
            triggered.
        :param func_args: Dictionary containing function/method argument names
            and values as key-value pairs. A function/method specified with
            the "func_name" argument will be invoked with these arguments.
        :param func_arg_serializers: Dictionary containing function/method
            argument names and serializers for argument values as key-value
            pairs. Each serializer is a full path to a subclass of
            :class:'mistral_lib.serialization.Serializer' that is capable
            of serializing and deserializing of a corresponding argument value.
            Optional. Serializers must be specified only for those arguments
            whose values can't be saved into a persistent storage as is and
            they need to be converted first into a value of a primitive type.

        """

        if not func_name:
            raise RuntimeError("'target_method_name' must be provided.")

        self.run_after = run_after
        self.target_factory_func_name = target_factory_func_name
        self.func_name = func_name
        self.func_args = func_args or {}
        self.func_arg_serializers = func_arg_serializers
