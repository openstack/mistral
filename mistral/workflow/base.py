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
from mistral.engine1 import states
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral.workbook import parser as spec_parser

LOG = logging.getLogger(__name__)


class WorkflowHandler(object):
    """Workflow Handler base class.

    Different workflow handler implement different workflow algorithms.
    In practice it may actually mean that there may be multiple ways of
    describing workflow models (and even languages) that will be supported
    by Mistral.
    """

    def __init__(self, exec_db):
        """Creates new workflow handler.

        :param exec_db: Execution.
        """
        self.exec_db = exec_db
        self.wf_spec = spec_parser.get_workflow_spec(exec_db.wf_spec)

    @abc.abstractmethod
    def start_workflow(self, **kwargs):
        """Starts workflow.

        Given a workflow specification this method makes required analysis
        according to this workflow type rules and identifies a list of
        tasks that can be scheduled for execution.
        :param kwargs: Additional parameters specific to workflow type.
        :return: List of tasks that can be scheduled for execution.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def on_task_result(self, task_db, task_result):
        """Handles event of arriving a task result.

        Given task result performs analysis of the workflow execution and
        identifies tasks that can be scheduled for execution.
        :param task_db: Task that the result corresponds to.
        :param task_result: Task result.
        :return  List of tasks that can be scheduled for execution.
        """
        raise NotImplementedError

    def is_stopped_or_finished(self):
        return states.is_stopped_or_finished(self.exec_db.state)

    def stop_workflow(self):
        """Stops workflow this handler is associated with.

        :return: Execution object.
        """
        self._set_execution_state(states.STOPPED)

        return self.exec_db

    def resume_workflow(self):
        """Resumes workflow this handler is associated with.

        :return: Tasks available to run.
        """
        self._set_execution_state(states.RUNNING)

        # TODO(rakhmerov): A concrete handler should also find tasks to run.

        return []

    def _set_execution_state(self, state):
        cur_state = self.exec_db.state

        if states.is_valid_transition(cur_state, state):
            self.exec_db.state = state
        else:
            msg = "Can't change workflow state [execution=%s," \
                  " state=%s -> %s]" % (self.exec_db, cur_state, state)
            raise exc.WorkflowException(msg)


class FlowControl(object):
    """Flow control structure.

    Expresses a control structure that influences the way how workflow
    execution goes at a certain point.
    """

    def decide(self, upstream_tasks, downstream_tasks):
        """Makes a decision in a form of changed states of downstream tasks.

        :param upstream_tasks: Upstream workflow tasks.
        :param downstream_tasks: Downstream workflow tasks.
        :return: Dictionary {task: state} for those tasks whose states
            have changed. {task} is a subset of {downstream_tasks}.
        """
        raise NotImplementedError
