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

"""Script to start instance of Task Executor."""

import sys
from oslo.config import cfg
from mistral import config
from mistral.openstack.common import log as logging
from mistral.engine.scalable.executor import executor

LOG = logging.getLogger('mistral.cmd.task_executor')


def main():
    try:
        config.parse_args()
        logging.setup('Mistral')

        rabbit_opts = cfg.CONF.rabbit

        executor.start(rabbit_opts)

        LOG.info("Mistral Task Executor is listening RabbitMQ"
                 " [host=%s, port=%s, task_queue=%s]" %
                 (rabbit_opts.rabbit_host,
                  rabbit_opts.rabbit_port,
                  rabbit_opts.rabbit_task_queue))
    except RuntimeError, e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


if __name__ == '__main__':
    main()
