# Copyright 2014 - Mirantis, Inc.
# Copyright 2014 - StackStorm, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
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
import copy
from oslo.config import cfg
import six

from mistral.db.v2 import api as db_api
from mistral.engine1 import policies
from mistral.engine1 import rpc
from mistral.engine1 import utils as e_utils
from mistral import expressions as expr
from mistral.openstack.common import log as logging
from mistral.services import action_manager as a_m
from mistral import utils
from mistral.workbook import parser as spec_parser
from mistral.workflow import data_flow
from mistral.workflow import for_each
from mistral.workflow import states


LOG = logging.getLogger(__name__)
WF_TRACE = logging.getLogger(cfg.CONF.workflow_trace_log_name)


def _log_execution_state_change(name, from_state, to_state):
    WF_TRACE.info("Execution of workflow '%s' [%s -> %s]"
                  % (name, from_state, to_state))


@six.add_metaclass(abc.ABCMeta)
class EngineCommand(object):
    """Engine command interface."""

    def run_local(self, exec_db, wf_handler, cause_task_db=None):
        """Runs local part of the command.

        "Local" means that the code can be performed within a scope
        of an opened DB transaction. For example, for all commands
        that simply change a state of execution (e.g. depending on
        some conditions) it's enough to implement only this method.

        :param exec_db: Workflow execution DB object.
        :param wf_handler: Workflow handler currently being used.
        :param cause_task_db: Task that caused the command to run.
        :return False if engine should stop further command processing,
            True otherwise.
        """
        return True

    def run_remote(self, exec_db, wf_handler, cause_task_db=None):
        """Runs remote part of the command.

        "Remote" means that the code cannot be performed within a scope
        of an opened DB transaction. All commands that deal with remote
        invocations should implement this method. However, they may also
        need to implement "run_local" if they need to do something with
        DB state of execution and/or tasks.

        :param exec_db: Workflow execution DB object.
        :param wf_handler: Workflow handler currently being used.
        :param cause_task_db: Task that caused the command to run.
        :return False if engine should stop further command processing,
            True otherwise.
        """
        return True


class Noop(EngineCommand):
    """No-op command."""
    def run_local(self, exec_db, wf_handler, cause_task_db=None):
        pass

    def run_remote(self, exec_db, wf_handler, cause_task_db=None):
        pass


class RunTask(EngineCommand):
    def __init__(self, task_spec, task_db=None):
        self.task_spec = task_spec
        self.task_db = task_db

        if task_db:
            self.exec_db = task_db.execution

    def run_local(self, exec_db, wf_handler, cause_task_db=None):
        if self.task_db and self.task_db.state == states.IDLE:
            LOG.debug('Resuming workflow task: %s' % self.task_spec)
            self.task_db.state = states.RUNNING

            return True

        LOG.debug('Running workflow task: %s' % self.task_spec)

        self._prepare_task(exec_db, wf_handler, cause_task_db)
        self._before_task_start(wf_handler.wf_spec)

        if exec_db.state == states.RUNNING:
            return True

        return False

    def _prepare_task(self, exec_db, wf_handler, cause_task_db):
        if self.task_db:
            return

        self.task_db = self._create_db_task(exec_db)
        self.exec_db = self.task_db.execution

        # Evaluate Data Flow properties ('input', 'in_context').
        data_flow.prepare_db_task(
            self.task_db,
            self.task_spec,
            wf_handler.get_upstream_tasks(self.task_spec),
            exec_db,
            cause_task_db
        )

    def _before_task_start(self, wf_spec):
        for p in policies.build_policies(self.task_spec.get_policies(),
                                         wf_spec):
            p.before_task_start(self.task_db, self.task_spec)

    def _create_db_task(self, exec_db):
        return db_api.create_task({
            'execution_id': exec_db.id,
            'name': self.task_spec.get_name(),
            'state': states.RUNNING,
            'spec': self.task_spec.to_dict(),
            'input': None,
            'in_context': None,
            'output': None,
            'runtime_context': None,
            'wf_name': exec_db.wf_name,
            'project_id': exec_db.project_id
        })

    def run_remote(self, exec_db, wf_handler, cause_task_db=None):
        self._run_task()

        return True

    def _run_task(self):
        # Policies could possibly change task state.
        if self.task_db.state != states.RUNNING:
            return

        if self.task_spec.get_action_name():
            WF_TRACE.info("Task '%s' is RUNNING [action_name = %s]"
                          % (self.task_db.name,
                             self.task_spec.get_action_name()))

            self._run_action()
        elif self.task_spec.get_workflow_name():
            WF_TRACE.info("Task '%s' is RUNNING [workflow_name = %s]"
                          % (self.task_db.name,
                             self.task_spec.get_workflow_name()))

            self._run_workflow()

    def _run_action(self):
        exec_db = self.exec_db
        wf_spec = spec_parser.get_workflow_spec(exec_db.wf_spec)

        action_spec_name = self.task_spec.get_action_name()

        action_db = e_utils.resolve_action(
            exec_db.wf_name,
            wf_spec.get_name(),
            action_spec_name
        )

        action_input = self.task_db.input or {}

        if action_db.spec:
            # Ad-hoc action.
            action_spec = spec_parser.get_action_spec(action_db.spec)

            base_name = action_spec.get_base()

            action_db = e_utils.resolve_action(
                exec_db.wf_name,
                wf_spec.get_name(),
                base_name
            )

            base_input = action_spec.get_base_input()

            if base_input:
                action_input = expr.evaluate_recursively(
                    base_input,
                    action_input
                )
            else:
                action_input = {}

        target = expr.evaluate_recursively(
            self.task_spec.get_target(),
            utils.merge_dicts(
                copy.copy(self.task_db.input),
                copy.copy(self.task_db.in_context)
            )
        )

        if a_m.has_action_context(
                action_db.action_class, action_db.attributes or {}):
            action_input.update(a_m.get_action_context(self.task_db))

        for_each_spec = self.task_spec.get_for_each()

        if for_each_spec:
            action_input_collection = for_each.calc_for_each_input(
                action_input
            )
            for a_input in action_input_collection:
                rpc.get_executor_client().run_action(
                    self.task_db.id,
                    action_db.action_class,
                    action_db.attributes or {},
                    expr.evaluate_recursively(
                        self.task_spec.get_input(),
                        utils.merge_dicts(
                            copy.copy(a_input),
                            copy.copy(self.task_db.in_context)
                        )
                    ),
                    target
                )

        else:
            rpc.get_executor_client().run_action(
                self.task_db.id,
                action_db.action_class,
                action_db.attributes or {},
                action_input,
                target
            )

    def _run_workflow(self):
        parent_exec_db = self.exec_db
        parent_wf_spec = spec_parser.get_workflow_spec(parent_exec_db.wf_spec)

        wf_spec_name = self.task_spec.get_workflow_name()

        wf_db = e_utils.resolve_workflow(
            parent_exec_db.wf_name,
            parent_wf_spec.get_name(),
            wf_spec_name
        )

        wf_spec = spec_parser.get_workflow_spec(wf_db.spec)

        wf_input = self.task_db.input

        start_params = {'parent_task_id': self.task_db.id}

        for k, v in wf_input.items():
            if k not in wf_spec.get_input():
                start_params[k] = v
                del wf_input[k]

        rpc.get_engine_client().start_workflow(
            wf_db.name,
            wf_input,
            **start_params
        )


class FailWorkflow(EngineCommand):
    def run_local(self, exec_db, wf_handler, cause_task_db=None):
        _log_execution_state_change(
            exec_db.wf_name,
            exec_db.state,
            states.ERROR
        )

        exec_db.state = states.ERROR

        return False

    def run_remote(self, exec_db, wf_handler, cause_task_db=None):
        return False


class SucceedWorkflow(EngineCommand):
    def run_local(self, exec_db, wf_handler, cause_task_db=None):
        _log_execution_state_change(
            exec_db.wf_name,
            exec_db.state,
            states.SUCCESS
        )

        exec_db.state = states.SUCCESS

        return False

    def run_remote(self, exec_db, wf_handler, cause_task_db=None):
        return False


class PauseWorkflow(EngineCommand):
    def run_local(self, exec_db, wf_handler, cause_task_db=None):
        _log_execution_state_change(
            exec_db.wf_name,
            exec_db.state,
            states.PAUSED
        )

        wf_handler.pause_workflow()

        return False

    def run_remote(self, exec_db, wf_handler, cause_task_db=None):
        return False


class RollbackWorkflow(EngineCommand):
    def run_local(self, exec_db, wf_handler, cause_task_db=None):
        return True

    def run_remote(self, exec_db, wf_handler, cause_task_db=None):
        return True


RESERVED_COMMANDS = {
    'noop': Noop,
    'fail': FailWorkflow,
    'succeed': SucceedWorkflow,
    'pause': PauseWorkflow,
    'rollback': PauseWorkflow
}


def get_reserved_command(cmd_name):
    return RESERVED_COMMANDS[cmd_name]() if cmd_name in RESERVED_COMMANDS \
        else None
