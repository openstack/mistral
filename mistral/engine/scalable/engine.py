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

from oslo import messaging
from oslo.config import cfg
from mistral.openstack.common import log as logging
from mistral.engine.scalable.executor import client
from mistral.engine import abstract_engine as abs_eng


LOG = logging.getLogger(__name__)


class ScalableEngine(abs_eng.AbstractEngine):
    @classmethod
    def _notify_task_executors(cls, tasks):
        # TODO(m4dcoder): Use a pool for transport and client
        if not cls.transport:
            cls.transport = messaging.get_transport(cfg.CONF)
        ex_client = client.ExecutorClient(cls.transport)
        for task in tasks:
            # TODO(m4dcoder): Fill request context argument with auth info
            context = {}
            ex_client.handle_task(context, task=task)
            LOG.info("Submitted task for execution: '%s'" % task)

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
