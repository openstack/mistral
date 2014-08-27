# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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

from mistral.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class Action(object):
    """Action.

    Action is a means in Mistral to perform some useful work associated with
    a workflow during its execution. Every workflow task is configured with
    an action and when the task runs it eventually delegates to the action.
    When it happens task parameters get evaluated (calculating expressions,
    if any) and are treated as action parameters. So in a regular general
    purpose languages terminology action is a method declaration and task is
    a method call.

    Base action class initializer doesn't have arguments. However, concrete
    action classes may have any number of parameters defining action behavior.
    These parameters must correspond to parameters declared in action
    specification (e.g. using DSL or others).
    Action initializer may have a conventional argument with name
    "action_context". If it presents then action factory will fill it with
    a dictionary containing contextual information like execution identifier,
    workbook name and other that may be needed for some specific action
    implementations.
    """

    @abc.abstractmethod
    def run(self):
        """Run action logic.

        :return: result of the action. Note that for asynchronous actions
        it should always be None, however, if even it's not None it will be
        ignored by a caller.

        In case if action failed this method must throw a ActionException
        to indicate that.
        """
        pass

    @abc.abstractmethod
    def test(self):
        """Returns action test result.

        This method runs in test mode as a test version of method run() to
        generate and return a representative test result. It's basically a
        contract for action 'dry-run' behavior specifically useful for
        testing and workflow designing purposes.

        :return: Representative action result.
        """
        pass

    def is_sync(self):
        """Returns True if the action is synchronous, otherwise False.

        :return: True if the action is synchronous and method run() returns
            final action result. Otherwise returns False which means that
            a result of method run() should be ignored and a real action
            result is supposed to be delivered in an asynchronous manner
            using public API. By default, if a concrete implementation
            doesn't override this method then the action is synchronous.
        """
        return True
