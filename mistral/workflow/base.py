# Copyright 2014 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from mistral.engine1 import commands
from mistral import exceptions as exc
from mistral.openstack.common import log as logging
from mistral import utils
from mistral.utils import wf_trace
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import states
from mistral.workflow import utils as wf_utils
from mistral.workflow import with_items


LOG = logging.getLogger(__name__)


class WorkflowHandler(object):
    """Workflow Handler base class.

    Different workflow handler implement different workflow algorithms.
    In practice it may actually mean that there may be multiple ways of
    describing workflow models (and even languages) that will be supported
    by Mistral.
    """

    def __init__(self, wf_ex):
        """Creates new workflow handler.

        :param wf_ex: Execution.
        """
        self.wf_ex = wf_ex
        self.wf_spec = spec_parser.get_workflow_spec(wf_ex.spec)

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

    def on_task_result(self, task_ex, result):
        """Handles event of arriving a task result.

        Given task result performs analysis of the workflow execution and
        identifies commands (including tasks) that can be scheduled for
        execution.
        :param task_ex: Task that the result corresponds to.
        :param result: Task action/workflow result.
            Instance of mistral.workflow.utils.TaskResult
        :return List of engine commands that needs to be performed.
        """

        # Ignore if task already completed.
        if states.is_completed(task_ex.state):
            return []

        task_spec = self.wf_spec.get_tasks()[task_ex.name]

        prev_state = task_ex.state

        task_ex.state = self._determine_task_state(task_ex, task_spec, result)

        # TODO(rakhmerov): This needs to be fixed (the method should work
        # differently).
        task_ex.result = self._determine_task_result(
            task_spec,
            task_ex,
            result
        )

        self._log_result(task_ex, prev_state, task_ex.state, result)

        if self.is_paused_or_completed():
            return []

        cmds = self._find_next_commands(task_ex)

        if (task_ex.state == states.ERROR and
                not self._is_error_handled(task_ex)):
            if not self.is_paused_or_completed():
                # TODO(dzimine): pass task_ex.result when Model refactored.
                msg = str(task_ex.result.get('error', "Unknown"))

                self._set_execution_state(
                    states.ERROR,
                    "Failure caused by error in task '%s': %s"
                    % (task_ex.name, msg)
                )

            return []

        if not cmds and not wf_utils.find_running_tasks(self.wf_ex):
            # If there are no running tasks at this point we can conclude that
            # the workflow has finished.
            if not self.is_paused_or_completed():
                self._set_execution_state(states.SUCCESS)

            self.wf_ex.output = data_flow.evaluate_workflow_output(
                self.wf_spec,
                self._evaluate_workflow_final_context(task_ex)
            )

        return cmds

    def _log_result(self, task_ex, from_state, to_state, result):
        def _result_msg():
            if task_ex.state == states.ERROR:
                return "error = %s" % utils.cut(result.error)

            return "result = %s" % utils.cut(result.data)

        wf_trace.info(
            self.wf_ex,
            "Task '%s' [%s -> %s, %s]" %
            (task_ex.name, from_state, to_state, _result_msg())
        )

    @staticmethod
    def _determine_task_result(task_spec, task_ex, result):
        # TODO(rakhmerov): Think how 'with-items' can be better encapsulated.
        if task_spec.get_with_items():
            return with_items.get_result(task_ex, task_spec, result)
        else:
            return data_flow.evaluate_task_result(task_ex, task_spec, result)

    @staticmethod
    def _determine_task_state(task_ex, task_spec, result):
        state = states.ERROR if result.is_error() else states.SUCCESS

        # TODO(rakhmerov): Think how 'with-items' can be better encapsulated.
        if task_spec.get_with_items():
            # Change the index.
            with_items.do_step(task_ex)

            # Check if all iterations are completed.
            if with_items.is_iterations_incomplete(task_ex):
                state = states.RUNNING

        return state

    @abc.abstractmethod
    def _evaluate_workflow_final_context(self, cause_task_ex):
        """Evaluates final workflow context assuming that workflow has finished.

        :param cause_task_ex: Task that caused workflow completion.
        :return: Final workflow context.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _find_next_commands(self, task_ex):
        """Finds commands that should run next.

        A concrete algorithm of finding such tasks depends on a concrete
        workflow handler.
        :param task_ex: Task DB model causing the operation (completed).
        :return: List of engine commands.
        """
        raise NotImplementedError

    def _is_error_handled(self, task_ex):
        return False

    def _find_commands_to_resume(self, tasks):
        """Finds commands that should run after pause.

        :param tasks: List of task_ex instances.
        :return: List of engine commands.
        """
        def filter_task_cmds(cmds):
            return [cmd for cmd in cmds if isinstance(cmd, commands.RunTask)]

        def get_tasks_to_schedule(task_ex, schedule_tasks):
            """Finds tasks that should run after given task and searches them
            in DB. If there are no tasks in the DB, it should be scheduled
            now. If there are tasks in the DB, continue search to next tasks
            in workflow if this task is finished. If this task is in IDLE
            state, schedule it for resume.

            :param task_ex: Task DB.
            :param schedule_tasks: Task names from previous iteration.
            :return: List of task names that should be scheduled.
            """
            next_cmds = filter_task_cmds(self._find_next_commands(task_ex))
            next_t_names = [cmd.task_spec.get_name() for cmd in next_cmds]

            if states.is_completed(task_ex.state):
                for task_name in next_t_names:
                    task_spec = self.wf_spec.get_tasks()[task_name]
                    t_db = wf_utils.find_db_task(self.wf_ex, task_spec)

                    if not t_db:
                        schedule_tasks += [task_name]
                    else:
                        schedule_tasks += get_tasks_to_schedule(
                            t_db,
                            schedule_tasks
                        )
            elif states.is_idle(task_ex.state):
                schedule_tasks += [task_ex.name]

            return schedule_tasks

        params = self.wf_ex.start_params
        start_task_cmds = filter_task_cmds(
            self.start_workflow(**params if params else {})
        )

        task_names = []

        for cmd in start_task_cmds:
            task_ex = [t for t in tasks
                       if t.name == cmd.task_spec.get_name()][0]
            task_names += get_tasks_to_schedule(task_ex, [])

        schedule_cmds = []

        for t_name in task_names:
            t_spec = self.wf_spec.get_tasks()[t_name]
            t_db = wf_utils.find_db_task(self.wf_ex, t_spec)

            schedule_cmds += [commands.RunTask(t_spec, t_db)]

        return schedule_cmds

    def is_paused_or_completed(self):
        return states.is_paused_or_completed(self.wf_ex.state)

    def stop_workflow(self, state, message=None):
        """Completes workflow as succeeded or failed.

        Sets execution state to SUCCESS or ERROR. No more tasks will be
        scheduled. Running tasks won't be killed, but their results
        will be ignored.

        :param state: 'SUCCESS' or 'ERROR'
        :param message: State info text with context of the operation.

        :return: Execution object.
        """
        if state not in [states.SUCCESS, states.ERROR]:
            msg = ("Illegal state %s: provided while stopping workflow "
                   "execution id=%s. State can be  %s or %s. "
                   "Stop request IGNORED." %
                   (state, self.wf_ex.id, states.SUCCESS, states.ERROR))
            raise exc.WorkflowException(msg)

        self._set_execution_state(state, message)

        return self.wf_ex

    def pause_workflow(self):
        """Pauses workflow this handler is associated with.

        :return: Execution object.
        """
        self._set_execution_state(states.PAUSED)

        return self.wf_ex

    def resume_workflow(self):
        """Resumes workflow this handler is associated with.

        :return: List of engine commands that needs to be performed..
        """
        self._set_execution_state(states.RUNNING)

        tasks = self.wf_ex.task_executions

        if not all([t.state == states.RUNNING for t in tasks]):
            return self._find_commands_to_resume(tasks)

        return []

    @abc.abstractmethod
    def get_upstream_tasks(self, task_spec):
        """Gets workflow upstream tasks for the given task.

        :param task_spec: Task specification.
        :return: List of upstream task specifications for the given task spec.
        """
        raise NotImplementedError

    def _set_execution_state(self, state, state_info=None):
        cur_state = self.wf_ex.state

        if states.is_valid_transition(cur_state, state):
            wf_trace.info(
                self.wf_ex,
                "Execution of workflow '%s' [%s -> %s]"
                % (self.wf_ex.workflow_name, cur_state, state)
            )
            self.wf_ex.state = state
            self.wf_ex.state_info = state_info
        else:
            msg = ("Can't change workflow execution state from %s to %s. "
                   "[workflow=%s, execution_id=%s]" %
                   (cur_state, state, self.wf_ex.wf_name, self.wf_ex.id))
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
