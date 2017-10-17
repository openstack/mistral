# Copyright 2013 - Mirantis, Inc.
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

from oslo_config import cfg
import oslo_middleware.cors as cors_middleware
import osprofiler.web
import pecan

from mistral.api import access_control
from mistral import config as m_config
from mistral import context as ctx
from mistral.db.v2 import api as db_api_v2
from mistral.rpc import base as rpc
from mistral.service import coordination
from mistral.services import periodic


def get_pecan_config():
    # Set up the pecan configuration.
    opts = cfg.CONF.pecan

    cfg_dict = {
        "app": {
            "root": opts.root,
            "modules": opts.modules,
            "debug": opts.debug,
            "auth_enable": opts.auth_enable
        }
    }

    return pecan.configuration.conf_from_dict(cfg_dict)


def setup_app(config=None):
    if not config:
        config = get_pecan_config()

    m_config.set_config_defaults()

    app_conf = dict(config.app)

    db_api_v2.setup_db()

    # TODO(rakhmerov): Why do we run cron triggers in the API layer?
    # Should we move it to engine?s
    if cfg.CONF.cron_trigger.enabled:
        periodic.setup()

    coordination.Service('api_group').register_membership()

    app = pecan.make_app(
        app_conf.pop('root'),
        hooks=lambda: [ctx.AuthHook(), ctx.ContextHook()],
        logging=getattr(config, 'logging', {}),
        **app_conf
    )

    # Set up access control.
    app = access_control.setup(app)

    # TODO(rakhmerov): need to get rid of this call.
    # Set up RPC related flags in config
    rpc.get_transport()

    # Set up profiler.
    if cfg.CONF.profiler.enabled:
        app = osprofiler.web.WsgiMiddleware(
            app,
            hmac_keys=cfg.CONF.profiler.hmac_keys,
            enabled=cfg.CONF.profiler.enabled
        )

    # Create a CORS wrapper, and attach mistral-specific defaults that must be
    # included in all CORS responses.
    return cors_middleware.CORS(app, cfg.CONF)


def init_wsgi():
    # By default, oslo.config parses the CLI args if no args is provided.
    # As a result, invoking this wsgi script from gunicorn leads to the error
    # with argparse complaining that the CLI options have already been parsed.
    m_config.parse_args(args=[])

    return setup_app()
