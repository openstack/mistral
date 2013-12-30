#!/usr/bin/env python
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

import sys
from mistralclient.api import client as cl

client = cl.Client(project_name="mistral",
                   mistral_url="http://localhost:8989/v1")

WB_NAME = "my_workbook"


def find_execution():
    executions = client.executions.list(WB_NAME)

    if len(executions) == 0:
        return None

    for e in executions:
        if e.state == "RUNNING":
            return e

    return None


def find_task(execution_id):
    tasks = client.tasks.list(WB_NAME, execution_id)

    if len(tasks) == 0:
        return None

    for t in tasks:
        if t.state == "RUNNING":
            return t

    return None


execution = find_execution()

if not execution:
    print "Unable to find running executions."
    sys.exit(0)

print "Updating execution: %s" % execution

task = find_task(execution.id)
if not task:
    print "Unable to find running tasks for execution: %s" % execution
    sys.exit(0)

print "Setting task to SUCCESS state: %s" % task

task = client.tasks.update(WB_NAME, execution.id, task.id, "SUCCESS")

print "Updated task: %s" % task

execution = client.executions.get(WB_NAME, task.execution_id)

print "Updated execution: %s" % execution
