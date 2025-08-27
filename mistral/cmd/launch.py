#!/usr/bin/env python
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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
POSSIBLE_TOPDIR = os.path.normpath(
    os.path.join(
        os.path.abspath(sys.argv[0]),
        os.pardir,
        os.pardir
    )
)

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
from mistral.notifiers import notification_server
from mistral.rpc import base as rpc
from mistral import version


CONF = cfg.CONF
SERVER_PROCESS_MANAGER = None

LOG = logging.getLogger(__name__)


def launch_process(server, workers=1):
    try:
        # NOTE(amorin) it is recommended to have only one ProcessLauncher
        # See https://docs.openstack.org/oslo.service/latest/user/usage.html
        global SERVER_PROCESS_MANAGER

        if not SERVER_PROCESS_MANAGER:
            SERVER_PROCESS_MANAGER = service.ProcessLauncher(
                CONF,
            )

        SERVER_PROCESS_MANAGER.launch_service(server, workers=workers)
    except Exception as e:
        sys.stderr.write("ERROR: %s\n" % e)
        sys.exit(1)


def launch_executor():
    launch_process(executor_server.get_oslo_service())


def launch_engine():
    launch_process(engine_server.get_oslo_service())


def launch_event_engine():
    launch_process(event_engine_server.get_oslo_service())


def launch_notifier():
    launch_process(notification_server.get_oslo_service())


def launch_api():
    server = api_service.WSGIService('mistral_api')

    launch_process(server, workers=server.workers)


def launch_any(options):
    for option in options:
        LAUNCH_OPTIONS[option]()

    global SERVER_PROCESS_MANAGER

    # Wait for the services to finish now
    # This main process will do nothing starting from now
    if SERVER_PROCESS_MANAGER:
        SERVER_PROCESS_MANAGER.wait()


# Map cli options to appropriate functions. The cli options are
# registered in mistral's config.py.
LAUNCH_OPTIONS = {
    'api': launch_api,
    'engine': launch_engine,
    'executor': launch_executor,
    'event-engine': launch_event_engine,
    'notifier': launch_notifier
}


MISTRAL_TITLE = r"""
|\\\    //|           ||                       ||
||\\\  //||      __   ||      __      __       ||
|| \\\// || ||  //  ||||||  ||  \\  //  \\     ||
||  \\/  ||     \\    ||    ||     ||    \\    ||
||       || ||   \\   ||    ||     ||    /\\   ||
||       || || __//   ||_// ||      \\__// \\_ ||

Mistral Workflow Service, version %s
""" % version.version_string


def _get_server():
    server = cfg.CONF.server
    if 'all' in server:
        return set(LAUNCH_OPTIONS.keys())
    return set(cfg.CONF.server)


def print_server_info():
    print(MISTRAL_TITLE)

    comp_str = "[%s]" % ','.join(_get_server())
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
        CONF.register_cli_opts(config.CLI_OPTS)
        config.parse_args(get_properly_ordered_parameters())
        print_server_info()
        logging.setup(CONF, 'Mistral')
        rpc.get_transport()
        launch_any(_get_server())

    except RuntimeError as excp:
        sys.stderr.write("ERROR: %s\n" % excp)
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
