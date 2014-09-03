# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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

from mistral.engine1 import base


def build_policies(policies_spec):
    if not policies_spec:
        return []

    policies = [
        build_wait_before_policy(policies_spec),
        build_wait_after_policy(policies_spec),
        build_retry_policy(policies_spec)
    ]

    return filter(None, policies)


def build_wait_before_policy(policies_spec):
    wait_before = policies_spec.get_wait_before()

    return WaitBeforePolicy(wait_before) if wait_before > 0 else None


def build_wait_after_policy(policies_spec):
    wait_after = policies_spec.get_wait_after()

    return WaitAfterPolicy(wait_after) if wait_after > 0 else None


def build_retry_policy(policies_spec):
    retry = policies_spec.get_retry()

    if not retry:
        return None

    return RetryPolicy(
        retry.get_count(),
        retry.get_delay(),
        retry.get_break_on()
    )


class WaitBeforePolicy(base.TaskPolicy):
    def __init__(self, delay):
        self.delay = delay

    def before_task_start(self, task_db, task_spec, exec_db, wf_spec):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError


class WaitAfterPolicy(base.TaskPolicy):
    def __init__(self, delay):
        self.delay = delay

    def after_task_complete(self, task_db, task_spec, exec_db, wf_spec):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError


class RetryPolicy(base.TaskPolicy):
    def __init__(self, count, delay, break_on):
        self.count = count
        self.delay = delay
        self.break_on = break_on

    def before_task_start(self, task_db, task_spec, exec_db, wf_spec):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError

    def after_task_complete(self, task_db, task_spec, exec_db, wf_spec):
        # TODO(rakhmerov): Implement.
        raise NotImplementedError
