# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

"""Valid task and workflow states."""

IDLE = 'IDLE'
RUNNING = 'RUNNING'
SUCCESS = 'SUCCESS'
ERROR = 'ERROR'
STOPPED = 'STOPPED'
DELAYED = 'DELAYED'

_ALL = [IDLE, RUNNING, SUCCESS, ERROR, STOPPED, DELAYED]


def is_valid(state):
    return state in _ALL


def is_finished(state):
    return state in [SUCCESS, ERROR]


def is_stopped_or_finished(state):
    return state == STOPPED or is_finished(state)
