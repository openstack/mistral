#!/usr/bin/env python
# Copyright 2016 - Brocade Communications Systems, Inc.
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

import eventlet


eventlet.monkey_patch(
    os=True,
    select=True,
    socket=True,
    thread=False if '--use-debugger' in sys.argv else True,
    time=True)


import os


# If ../mistral/__init__.py exists, add ../ to Python search path, so that
# it will override what happens to be installed in /usr/(local/)lib/python...
POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(POSSIBLE_TOPDIR, 'mistral', '__init__.py')):
    sys.path.insert(0, POSSIBLE_TOPDIR)

from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import service

from mistral.api import service as api_service
from mistral import config
from mistral.engine import engine_server
from mistral.event_engine import event_engine_server
from mistral.executors import executor_server
from mistral.rpc import base as rpc
from mistral import version


CONF = cfg.CONF


def launch_executor():
    try:
        launcher = service.ServiceLauncher(CONF)

        launcher.launch_service(executor_server.get_oslo_service())

        launcher.wait()
    except RuntimeError as e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


def launch_engine():
    try:
        launcher = service.ServiceLauncher(CONF)

        launcher.launch_service(engine_server.get_oslo_service())

        launcher.wait()
    except RuntimeError as e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


def launch_event_engine():
    try:
        launcher = service.ServiceLauncher(CONF)

        launcher.launch_service(event_engine_server.get_oslo_service())

        launcher.wait()
    except RuntimeError as e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


def launch_api():
    launcher = service.ProcessLauncher(cfg.CONF)

    server = api_service.WSGIService('mistral_api')

    launcher.launch_service(server, workers=server.workers)

    launcher.wait()


def launch_any(options):
    # Launch the servers on different threads.
    threads = [eventlet.spawn(LAUNCH_OPTIONS[option])
               for option in options]

    [thread.wait() for thread in threads]


# Map cli options to appropriate functions. The cli options are
# registered in mistral's config.py.
LAUNCH_OPTIONS = {
    'api': launch_api,
    'engine': launch_engine,
    'executor': launch_executor,
    'event-engine': launch_event_engine
}


MISTRAL_TITLE = """
|\\\    //| //   // |||||| |||\\\       /\      ||
||\\\  //||    //     ||   ||  ||     //\\\     ||
|| \\\// || || ||     ||   || //     //  \\\    ||
||  \/  || ||  \\\    ||   || \\\    //-||-\\\   ||
||      || ||   ||   ||   ||  ||  //      \\\  ||
||      || || _//    ||   ||  || //        \\\ |||||

Mistral Workflow Service, version %s
""" % version.version_string()


def print_server_info():
    print(MISTRAL_TITLE)

    comp_str = ("[%s]" % ','.join(LAUNCH_OPTIONS)
                if cfg.CONF.server == ['all'] else cfg.CONF.server)

    print('Launching server components %s...' % comp_str)


def get_properly_ordered_parameters():
    """Orders launch parameters in the right order.

    In oslo it's important the order of the launch parameters.
    if --config-file came after the command line parameters the command
    line parameters are ignored.
    So to make user command line parameters are never ignored this method
    moves --config-file to be always first.
    """
    args = sys.argv[1:]

    for arg in sys.argv[1:]:
        if arg == '--config-file' or arg.startswith('--config-file='):
            if "=" in arg:
                conf_file_value = arg.split("=", 1)[1]
            else:
                conf_file_value = args[args.index(arg) + 1]
                args.remove(conf_file_value)
            args.remove(arg)
            args.insert(0, "--config-file")
            args.insert(1, conf_file_value)

    return args


def main():
    try:
        config.parse_args(get_properly_ordered_parameters())
        print_server_info()

        logging.setup(CONF, 'Mistral')

        # Please refer to the oslo.messaging documentation for transport
        # configuration. The default transport for oslo.messaging is
        # rabbitMQ. The available transport drivers are listed in the
        # setup.cfg file in oslo.messaging under the entry_points section for
        # oslo.messaging.drivers. The transport driver is specified using the
        # rpc_backend option in the default section of the oslo configuration
        # file. The expected value for the rpc_backend is one of the key
        # values available for the oslo.messaging.drivers (i.e. rabbit, fake).
        # There are additional options such as ssl and credential that can be
        # specified depending on the driver.  Please refer to the driver
        # implementation for those additional options. It's important to note
        # that the "fake" transport should only be used if "all" the Mistral
        # servers are launched on the same process. Otherwise, messages do not
        # get delivered if the Mistral servers are launched on different
        # processes because the "fake" transport is using an in process queue.
        rpc.get_transport()

        if cfg.CONF.server == ['all']:
            # Launch all servers.
            launch_any(LAUNCH_OPTIONS.keys())
        else:
            # Validate launch option.
            if set(cfg.CONF.server) - set(LAUNCH_OPTIONS.keys()):
                raise Exception('Valid options are all or any combination of '
                                ', '.join(LAUNCH_OPTIONS.keys()))

            # Launch distinct set of server(s).
            launch_any(set(cfg.CONF.server))

    except RuntimeError as excp:
        sys.stderr.write("ERROR: %s\n" % excp)
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
