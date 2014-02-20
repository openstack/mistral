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

from mistral.openstack.common import log as logging
from mistral.db import api as db_api
from mistral import exceptions as exc
from mistral.engine import engine
from mistral.engine import states
from mistral.engine.actions import action_factory as a_f
from mistral.engine.actions import action_helper as a_h

LOG = logging.getLogger(__name__)

# TODO(rakhmerov): Upcoming Data Flow changes:
# 1. Receive "in_context" along with task data.
# 2. Apply task input expression to "in_context" and calculate "input".


def do_task_action(task):
    LOG.info("Starting task action [task_id=%s, action='%s', service='%s'" %
             (task['id'], task['task_dsl']['action'], task['service_dsl']))
    action = a_f.create_action(task)
    if a_h.is_task_synchronous(task):
        action_result = action.run()
        state, result = a_h.extract_state_result(action, action_result)
        # TODO(nmakhotkin) save the result in the context with key
        # action.result_helper['store_as']

        if states.is_valid(state):
            return engine.convey_task_result(task['workbook_name'],
                                             task['execution_id'],
                                             task['id'], state, result)
        else:
            raise exc.EngineException("Action has returned invalid "
                                      "state: %s" % state)
    action.run()


def handle_task_error(task, exc):
    try:
        db_api.start_tx()
        try:
            db_api.execution_update(task['workbook_name'],
                                    task['execution_id'],
                                    {'state': states.ERROR})
            db_api.task_update(task['workbook_name'],
                               task['execution_id'],
                               task['id'],
                               {'state': states.ERROR})
            db_api.commit_tx()
        finally:
            db_api.end_tx()
    except Exception as e:
        LOG.exception(e)


def handle_task(channel, method, properties, body):
    channel.basic_ack(delivery_tag=method.delivery_tag)

    task = json.loads(body)
    try:
        LOG.info("Received a task from RabbitMQ: %s" % task)

        db_task = db_api.task_get(task['workbook_name'],
                                  task['execution_id'],
                                  task['id'])
        db_exec = db_api.execution_get(task['workbook_name'],
                                       task['execution_id'])

        if not db_exec or not db_task:
            return

        if db_exec['state'] != states.RUNNING or \
                db_task['state'] != states.IDLE:
            return

        do_task_action(db_task)
        db_api.task_update(task['workbook_name'],
                           task['execution_id'],
                           task['id'],
                           {'state': states.RUNNING})
    except Exception as exc:
        LOG.exception(exc)
        handle_task_error(task, exc)


def start(rabbit_opts):
    opts = rabbit_opts

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

        LOG.info("Waiting for task messages...")

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(handle_task,
                              queue=opts.rabbit_task_queue,
                              no_ack=False)

        channel.start_consuming()
    finally:
        conn.close()
