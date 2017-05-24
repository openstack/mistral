# Copyright 2018 - Extreme Networks, Inc.
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

from mistral.workflow import states


WORKFLOW_LAUNCHED = 'WORKFLOW_LAUNCHED'
WORKFLOW_SUCCEEDED = 'WORKFLOW_SUCCEEDED'
WORKFLOW_FAILED = 'WORKFLOW_FAILED'
WORKFLOW_CANCELLED = 'WORKFLOW_CANCELLED'
WORKFLOW_PAUSED = 'WORKFLOW_PAUSED'
WORKFLOW_RESUMED = 'WORKFLOW_RESUMED'

WORKFLOWS = [
    WORKFLOW_LAUNCHED,
    WORKFLOW_SUCCEEDED,
    WORKFLOW_FAILED,
    WORKFLOW_CANCELLED,
    WORKFLOW_PAUSED,
    WORKFLOW_RESUMED
]

TASK_LAUNCHED = 'TASK_LAUNCHED'
TASK_SUCCEEDED = 'TASK_SUCCEEDED'
TASK_FAILED = 'TASK_FAILED'
TASK_CANCELLED = 'TASK_CANCELLED'
TASK_PAUSED = 'TASK_PAUSED'
TASK_RESUMED = 'TASK_RESUMED'

TASKS = [
    TASK_LAUNCHED,
    TASK_SUCCEEDED,
    TASK_FAILED,
    TASK_CANCELLED,
    TASK_PAUSED,
    TASK_RESUMED
]

EVENTS = WORKFLOWS + TASKS

TASK_STATE_TRANSITION_MAP = {
    states.RUNNING: {
        'ANY': TASK_LAUNCHED,
        'IDLE': TASK_RESUMED,
        'PAUSED': TASK_RESUMED,
        'WAITING': TASK_RESUMED
    },
    states.SUCCESS: {'ANY': TASK_SUCCEEDED},
    states.ERROR: {'ANY': TASK_FAILED},
    states.CANCELLED: {'ANY': TASK_CANCELLED},
    states.PAUSED: {'ANY': TASK_PAUSED}
}


def identify_task_event(old_task_state, new_task_state):
    event_options = (
        TASK_STATE_TRANSITION_MAP[new_task_state]
        if new_task_state in TASK_STATE_TRANSITION_MAP
        else {}
    )

    if not event_options:
        return None

    event = (
        event_options[old_task_state]
        if old_task_state and old_task_state in event_options
        else event_options['ANY']
    )

    return event
