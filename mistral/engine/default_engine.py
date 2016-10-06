# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

from mistral import coordination
from mistral.db.v2 import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.engine import action_handler
from mistral.engine import base
from mistral.engine import workflow_handler as wf_handler
from mistral import exceptions
from mistral import utils as u
from mistral.workflow import states

LOG = logging.getLogger(__name__)


# Submodules of mistral.engine will throw NoSuchOptError if configuration
# options required at top level of this  __init__.py are not imported before
# the submodules are referenced.


class DefaultEngine(base.Engine, coordination.Service):
    def __init__(self, engine_client):
        self._engine_client = engine_client

        coordination.Service.__init__(self, 'engine_group')

    @u.log_exec(LOG)
    @profiler.trace('engine-start-workflow')
    def start_workflow(self, wf_identifier, wf_input, description='',
                       **params):
        with db_api.transaction():
            wf_ex = wf_handler.start_workflow(
                wf_identifier,
                wf_input,
                description,
                params
            )

            return wf_ex.get_clone()

    @u.log_exec(LOG)
    def start_action(self, action_name, action_input,
                     description=None, **params):
        with db_api.transaction():
            action = action_handler.build_action_by_name(action_name)

            action.validate_input(action_input)

            sync = params.get('run_sync')
            save = params.get('save_result')
            target = params.get('target')

            is_action_sync = action.is_sync(action_input)

            if sync and not is_action_sync:
                raise exceptions.InputException(
                    "Action does not support synchronous execution.")

            if not sync and (save or not is_action_sync):
                action.schedule(action_input, target)

                return action.action_ex.get_clone()

            output = action.run(action_input, target, save=False)

            state = states.SUCCESS if output.is_success() else states.ERROR

            if not save:
                # Action execution is not created but we need to return similar
                # object to a client anyway.
                return db_models.ActionExecution(
                    name=action_name,
                    description=description,
                    input=action_input,
                    output=output.to_dict(),
                    state=state
                )

            action_ex_id = u.generate_unicode_uuid()

            values = {
                'id': action_ex_id,
                'name': action_name,
                'description': description,
                'input': action_input,
                'output': output.to_dict(),
                'state': state,
            }

            return db_api.create_action_execution(values)

    @u.log_exec(LOG)
    @profiler.trace('engine-on-action-complete')
    def on_action_complete(self, action_ex_id, result, wf_action=False):
        with db_api.transaction():
            if wf_action:
                action_ex = db_api.get_workflow_execution(action_ex_id)
            else:
                action_ex = db_api.get_action_execution(action_ex_id)

            action_handler.on_action_complete(action_ex, result)

            return action_ex.get_clone()

    @u.log_exec(LOG)
    def pause_workflow(self, wf_ex_id):
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex_id)

            wf_handler.pause_workflow(wf_ex)

            return wf_ex.get_clone()

    @u.log_exec(LOG)
    def rerun_workflow(self, task_ex_id, reset=True, env=None):
        with db_api.transaction():
            task_ex = db_api.get_task_execution(task_ex_id)

            wf_ex = task_ex.workflow_execution

            wf_handler.rerun_workflow(wf_ex, task_ex, reset=reset, env=env)

            return wf_ex.get_clone()

    @u.log_exec(LOG)
    def resume_workflow(self, wf_ex_id, env=None):
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex_id)

            wf_handler.resume_workflow(wf_ex, env=env)

            return wf_ex.get_clone()

    @u.log_exec(LOG)
    def stop_workflow(self, wf_ex_id, state, message=None):
        with db_api.transaction():
            wf_ex = db_api.get_workflow_execution(wf_ex_id)

            wf_handler.stop_workflow(wf_ex, state, message)

            return wf_ex.get_clone()

    @u.log_exec(LOG)
    def rollback_workflow(self, wf_ex_id):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError
