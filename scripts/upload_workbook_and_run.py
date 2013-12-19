#!/usr/bin/env python

from mistralclient.api import client as cl

client = cl.Client(project_name="mistral",
                   mistral_url="http://localhost:8989/v1")

WB_NAME = "my_workbook"
TARGET_TASK = "my_task"
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

execution = client.executions.create(WB_NAME, TARGET_TASK)

print "execution: %s" % execution
