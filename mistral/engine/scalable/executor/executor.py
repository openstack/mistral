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

import pika

from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def handle_task(channel, method, properties, body):
    channel.basic_ack(delivery_tag=method.delivery_tag)

    LOG.info("Received a message from RabbitMQ: " + body)
    #TODO(rakhmerov): implement task execution logic
    # 1. Fetch task and execution state from DB
    # 2. If execution is in "RUNNING" state and task state is "IDLE"
    #   then do task action (send a signal)


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
