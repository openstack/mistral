# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import itertools

from mistral.policies import action
from mistral.policies import action_executions
from mistral.policies import base
from mistral.policies import cron_trigger
from mistral.policies import environment
from mistral.policies import event_trigger
from mistral.policies import execution
from mistral.policies import member
from mistral.policies import service
from mistral.policies import task
from mistral.policies import workbook
from mistral.policies import workflow


def list_rules():
    return itertools.chain(
        action.list_rules(),
        action_executions.list_rules(),
        base.list_rules(),
        cron_trigger.list_rules(),
        environment.list_rules(),
        event_trigger.list_rules(),
        execution.list_rules(),
        member.list_rules(),
        service.list_rules(),
        task.list_rules(),
        workbook.list_rules(),
        workflow.list_rules()
    )
