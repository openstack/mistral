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
