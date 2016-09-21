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

from mistral.api import service as mistral_service
from mistral import config
from mistral.db.v2 import api as db_api
from mistral.engine import default_engine as def_eng
from mistral.engine import default_executor as def_executor
from mistral.engine.rpc_backend import rpc
from mistral.services import event_engine
from mistral.services import expiration_policy
from mistral.services import scheduler
from mistral.utils import profiler
from mistral.utils import rpc_utils
from mistral import version


CONF = cfg.CONF


def launch_executor():
    profiler.setup('mistral-executor', cfg.CONF.executor.host)

    executor_v2 = def_executor.DefaultExecutor(rpc.get_engine_client())
    executor_endpoint = rpc.ExecutorServer(executor_v2)

    executor_server = rpc.get_rpc_server_driver()(
        rpc_utils.get_rpc_info_from_oslo(CONF.executor)
    )
    executor_server.register_endpoint(executor_endpoint)

    executor_v2.register_membership()

    try:
        executor_server.run(executor='threading')
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("Stopping executor service...")


def launch_engine():
    profiler.setup('mistral-engine', cfg.CONF.engine.host)

    engine_v2 = def_eng.DefaultEngine(rpc.get_engine_client())

    engine_endpoint = rpc.EngineServer(engine_v2)

    # Setup scheduler in engine.
    db_api.setup_db()
    scheduler.setup()

    # Setup expiration policy
    expiration_policy.setup()

    engine_server = rpc.get_rpc_server_driver()(
        rpc_utils.get_rpc_info_from_oslo(CONF.engine)
    )
    engine_server.register_endpoint(engine_endpoint)

    engine_v2.register_membership()

    try:
        # Note(ddeja): Engine needs to be run in default (blocking) mode
        # since using another mode may lead to deadlock.
        # See https://review.openstack.org/#/c/356343/
        # for more info.
        engine_server.run()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("Stopping engine service...")


def launch_event_engine():
    profiler.setup('mistral-event-engine', cfg.CONF.event_engine.host)

    event_eng = event_engine.EventEngine(rpc.get_engine_client())
    endpoint = rpc.EventEngineServer(event_eng)

    event_engine_server = rpc.get_rpc_server_driver()(
        rpc_utils.get_rpc_info_from_oslo(CONF.event_engine)
    )
    event_engine_server.register_endpoint(endpoint)

    event_eng.register_membership()

    try:
        event_engine_server.run()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("Stopping event_engine service...")


def launch_api():
    launcher = mistral_service.process_launcher()
    server = mistral_service.WSGIService('mistral_api')
    launcher.launch_service(server, workers=server.workers)
    launcher.wait()


def launch_any(options):
    # Launch the servers on different threads.
    threads = [eventlet.spawn(LAUNCH_OPTIONS[option])
               for option in options]

    print('Server started.')

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
                                'api, engine, and executor.')

            # Launch distinct set of server(s).
            launch_any(set(cfg.CONF.server))

    except RuntimeError as excp:
        sys.stderr.write("ERROR: %s\n" % excp)
        sys.exit(1)


if __name__ == '__main__':
    main()
