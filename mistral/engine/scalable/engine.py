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
from mistral.engine import abstract_engine as abs_eng


LOG = logging.getLogger(__name__)


class ScalableEngine(abs_eng.AbstractEngine):
    @classmethod
    def _notify_task_executors(cls, tasks):
        opts = cfg.CONF.rabbit

        creds = pika.PlainCredentials(opts.rabbit_user,
                                      opts.rabbit_password)
        params = pika.ConnectionParameters(opts.rabbit_host,
                                           opts.rabbit_port,
                                           opts.rabbit_virtual_host,
                                           creds)

        conn = pika.BlockingConnection(params)
        LOG.debug("Connected to RabbitMQ server [params=%s]" % params)

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

    @classmethod
    def _run_tasks(cls, tasks):
        # TODO(rakhmerov):
        # This call outside of DB transaction creates a window
        # when the engine may crash and DB will not be consistent with
        # the task message queue state. Need to figure out the best
        # solution to recover from this situation.
        # However, making this call in DB transaction is really bad
        # since it makes transaction much longer in time and under load
        # may overload DB with open transactions.
        cls._notify_task_executors(tasks)


def get_engine():
    return ScalableEngine
