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

import json

import pika
from oslo.config import cfg
from mistral.openstack.common import log as logging
from mistral.db import api as db_api
from mistral import dsl
from mistral.engine import exception
from mistral.engine import states
from mistral.engine.scalable import workflow


LOG = logging.getLogger(__name__)


def _notify_task_executors(tasks):
    opts = cfg.CONF.rabbit

    creds = pika.PlainCredentials(opts.rabbit_user,
                                  opts.rabbit_password)
    params = pika.ConnectionParameters(opts.rabbit_host,
                                       opts.rabbit_port,
                                       opts.rabbit_virtual_host,
                                       creds)

    conn = pika.BlockingConnection(params)
    LOG.info("Connected to RabbitMQ server [params=%s]" % params)

    try:
        channel = conn.channel()
        channel.queue_declare(queue=opts.rabbit_task_queue)

        for task in tasks:
            msg = json.dumps(task)
            channel.basic_publish(exchange='',
                                  routing_key=opts.rabbit_task_queue,
                                  body=msg)
            LOG.info("Submitted task for execution: '%s'" % msg)
    finally:
        conn.close()


def start_workflow_execution(workbook_name, target_task_name):
    wb = db_api.workbook_get(workbook_name)
    wb_dsl = dsl.Parser(wb.definition)

    dsl_tasks = workflow.find_workflow_tasks(wb_dsl, target_task_name)

    db_api.start_tx()

    try:
        # Persist execution and tasks in DB.
        execution = db_api.execution_create(workbook_name, {
            "workbook_name": workbook_name,
            "target_task": target_task_name,
            "state": states.RUNNING
        })

        tasks = []

        for dsl_task in dsl_tasks:
            task = db_api.task_create(workbook_name, execution["id"], {
                "workbook_name": workbook_name,
                "execution_id": execution["id"],
                "name": dsl_task["name"],
                "action": wb_dsl.get_action(dsl_task["action"]),
                "state": states.IDLE,
                "tags": dsl_task["tags"]
            })

            tasks.append(task)

        _notify_task_executors(tasks)

        db_api.commit_tx()
    finally:
        db_api.end_tx()
        pass


def stop_workflow_execution(workbook_name, execution_id):
    db_api.execution_update(workbook_name, execution_id,
                            {"state": states.STOPPED})


def convey_task_result(workbook_name, execution_id, task_id, state, result):
    db_api.start_tx()

    try:
        # Update task state
        task = db_api.task_update(workbook_name, execution_id, task_id,
                                  {"state": state, "result": result})

        if task["state"] == states.ERROR:
            db_api.execution_update(workbook_name, execution_id, {
                "state": states.ERROR
            })

            db_api.commit_tx()
            return

        execution = db_api.execution_get(workbook_name, execution_id)

        if states.is_stopped_or_finished(execution["state"]):
            # The execution has finished or stopped temporarily.
            db_api.commit_tx()
            return

        # Determine what tasks need to be started.
        tasks = db_api.tasks_get(workbook_name, execution_id)

        if workflow.is_finished(tasks):
            db_api.commit_tx()
            return

        _notify_task_executors(workflow.find_tasks_to_start(tasks))

        db_api.commit_tx()
    finally:
        db_api.end_tx()


def get_workflow_execution_state(workbook_name, execution_id):
    execution = db_api.execution_get(workbook_name, execution_id)

    if not execution:
        raise exception.EngineException("Workflow execution not found.")

    return execution["state"]


def get_task_state(workbook_name, execution_id, task_id):
    task = db_api.task_get(workbook_name, execution_id, task_id)

    if not task:
        raise exception.EngineException("Task not found.")

    return task["state"]
