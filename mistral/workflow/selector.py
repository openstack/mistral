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

from mistral.workflow import direct_workflow
from mistral.workflow import reverse_workflow

# TODO(rakhmerov): Take DSL versions into account.


def select_workflow_handler(workflow_spec):
    # TODO(rakhmerov): This algorithm is actually for DSL v2.
    wf_type = workflow_spec.type or 'direct'

    if wf_type == 'reverse':
        return reverse_workflow.ReverseWorkflowHandler

    if wf_type == 'direct':
        return direct_workflow.DirectWorkflowHandler

    return None
