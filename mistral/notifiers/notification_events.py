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
WORKFLOW_RERUN = 'WORKFLOW_RERUN'

WORKFLOWS = [
    WORKFLOW_LAUNCHED,
    WORKFLOW_SUCCEEDED,
    WORKFLOW_FAILED,
    WORKFLOW_CANCELLED,
    WORKFLOW_PAUSED,
    WORKFLOW_RESUMED,
    WORKFLOW_RERUN
]

TASK_LAUNCHED = 'TASK_LAUNCHED'
TASK_SUCCEEDED = 'TASK_SUCCEEDED'
TASK_FAILED = 'TASK_FAILED'
TASK_CANCELLED = 'TASK_CANCELLED'
TASK_PAUSED = 'TASK_PAUSED'
TASK_RESUMED = 'TASK_RESUMED'
TASK_RERUN = 'TASK_RERUN'
TASK_SKIPPED = 'TASK_SKIPPED'

TASKS = [
    TASK_LAUNCHED,
    TASK_SUCCEEDED,
    TASK_FAILED,
    TASK_CANCELLED,
    TASK_PAUSED,
    TASK_RESUMED,
    TASK_RERUN,
    TASK_SKIPPED
]

EVENTS = WORKFLOWS + TASKS

# Describes what state transition matches to what event.
_TASK_EVENT_MAP = {
    states.RUNNING: {
        'ANY': TASK_LAUNCHED,
        states.IDLE: TASK_RESUMED,
        states.PAUSED: TASK_RESUMED,
        states.WAITING: TASK_RESUMED,
        states.ERROR: TASK_RERUN

    },
    states.SUCCESS: {'ANY': TASK_SUCCEEDED},
    states.ERROR: {'ANY': TASK_FAILED},
    states.CANCELLED: {'ANY': TASK_CANCELLED},
    states.PAUSED: {'ANY': TASK_PAUSED},
    states.SKIPPED: {'ANY': TASK_SKIPPED}
}

# Describes what state transition matches to what event.
_WF_EVENT_MAP = {
    states.RUNNING: {
        'ANY': WORKFLOW_LAUNCHED,
        states.IDLE: WORKFLOW_LAUNCHED,
        states.PAUSED: WORKFLOW_RESUMED,
        states.ERROR: WORKFLOW_RERUN

    },
    states.SUCCESS: {'ANY': WORKFLOW_SUCCEEDED},
    states.ERROR: {'ANY': WORKFLOW_FAILED},
    states.CANCELLED: {'ANY': WORKFLOW_CANCELLED},
    states.PAUSED: {'ANY': WORKFLOW_PAUSED}
}


def _identify_event(from_state, to_state, event_map):
    event_options = (
        event_map[to_state]
        if to_state in event_map
        else {}
    )

    if not event_options:
        return None

    event = (
        event_options[from_state]
        if from_state and from_state in event_options
        else event_options['ANY']
    )

    return event


def identify_task_event(from_state, to_state):
    return _identify_event(from_state, to_state, _TASK_EVENT_MAP)


def identify_workflow_event(from_state, to_state):
    return _identify_event(from_state, to_state, _WF_EVENT_MAP)
