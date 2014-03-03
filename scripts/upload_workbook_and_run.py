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

import time

from mistralclient.api import client as cl

client = cl.Client(project_name="mistral",
                   mistral_url="http://localhost:8989/v1",
                   username="admin",
                   api_key="secrete",
                   auth_url="http://localhost:5000/v3")

WB_NAME = "my_workbook"
TASK = "my_task"
wb_list = client.workbooks.list()

wb = None
for item in wb_list:
    if item.name == WB_NAME:
        wb = item
        break

if not wb:
    wb = client.workbooks.create(WB_NAME,
                                 description="My test workbook",
                                 tags=["test"])

print "Created workbook: %s" % wb

with open("scripts/test.yaml") as definition_file:
    definition = definition_file.read()

client.workbooks.upload_definition(WB_NAME, definition)

print "\nUploaded workbook:\n\"\n%s\"\n" %\
      client.workbooks.get_definition(WB_NAME)

execution = client.executions.create(WB_NAME, TASK)

print "execution: %s" % execution

# wait until task is complete
for i in range(0, 20):
    execution = client.executions.get(WB_NAME, execution.id)
    print "execution: %s" % execution
    if execution.state == 'SUCCESS':
        break
    time.sleep(1)
