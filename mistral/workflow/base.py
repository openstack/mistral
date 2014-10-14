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

from oslo.config import cfg

from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral import utils
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states

LOG = logging.getLogger(__name__)
WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


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
    def start_workflow(self, **params):
        """Starts workflow.

        Given a workflow specification this method makes required analysis
        according to this workflow type rules and identifies a list of
        tasks that can be scheduled for execution.
        :param params: Additional parameters specific to workflow type.
        :return: List of engine commands that needs to be performed.
        """
        raise NotImplementedError

    def on_task_result(self, task_db, raw_result):
        """Handles event of arriving a task result.

        Given task result performs analysis of the workflow execution and
        identifies tasks that can be scheduled for execution.
        :param task_db: Task that the result corresponds to.
        :param raw_result: Raw task result that comes from action/workflow
        (before publisher). Instance of mistral.workflow.utils.TaskResult
        :return List of engine commands that needs to be performed.
        """

        # Ignore if task already completed.
        if states.is_finished(task_db.state):
            return []

        wf_trace_msg = "Task '%s' [%s -> " % (task_db.name, task_db.state)

        task_db.state = \
            states.ERROR if raw_result.is_error() else states.SUCCESS
        task_spec = self.wf_spec.get_tasks()[task_db.name]

        wf_trace_msg += "%s" % task_db.state
        if task_db.state == states.ERROR:
            wf_trace_msg += ", error = %s]" % utils.cut(raw_result.error)
            WF_TRACE.info(wf_trace_msg)
        else:
            wf_trace_msg += ", result = %s]" % utils.cut(raw_result.data)

        WF_TRACE.info(wf_trace_msg)

        task_db.output =\
            data_flow.evaluate_task_output(task_spec, raw_result)

        commands = self._find_next_commands(task_db)

        if task_db.state == states.ERROR and not commands:
            if not self.is_paused_or_finished():
                self._set_execution_state(states.ERROR)

            return []

        if len(commands) == 0:
            # If there are no running tasks at this point we can conclude that
            # the workflow has finished.
            if not self._find_running_tasks():
                if not self.is_paused_or_finished():
                    self._set_execution_state(states.SUCCESS)

                task_out_ctx = data_flow.evaluate_outbound_context(task_db)

                self.exec_db.output = data_flow.evaluate_workflow_output(
                    self.wf_spec,
                    task_out_ctx
                )

        return commands

    @abc.abstractmethod
    def _find_next_commands(self, task_db):
        """Finds commands that should run next.

        A concrete algorithm of finding such tasks depends on a concrete
        workflow handler.
        :param task_db: Task DB model causing the operation (completed).
        :return: List of engine commands.
        """
        raise NotImplementedError

    def is_paused_or_finished(self):
        return states.is_paused_or_finished(self.exec_db.state)

    def pause_workflow(self):
        """Stops workflow this handler is associated with.

        :return: Execution object.
        """
        self._set_execution_state(states.PAUSED)

        return self.exec_db

    def resume_workflow(self):
        """Resumes workflow this handler is associated with.

        :return: List of engine commands that needs to be performed..
        """
        self._set_execution_state(states.RUNNING)

        # TODO(rakhmerov): A concrete handler should also find tasks to run.

        return []

    @abc.abstractmethod
    def get_upstream_tasks(self, task_spec):
        """Gets workflow upstream tasks for the given task.

        :param task_spec: Task specification.
        :return: List of upstream task specifications for the given task spec.
        """
        raise NotImplementedError

    def _set_execution_state(self, state):
        cur_state = self.exec_db.state

        if states.is_valid_transition(cur_state, state):
            self.exec_db.state = state
        else:
            msg = "Can't change workflow state [execution=%s," \
                  " state=%s -> %s]" % (self.exec_db, cur_state, state)
            raise exc.WorkflowException(msg)

    def _find_running_tasks(self):
        return [t_db for t_db in self.exec_db.tasks
                if t_db.state == states.RUNNING]


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
