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
from oslo_log import log as logging
import oslo_middleware.cors as cors_middleware
from oslo_middleware import healthcheck
from oslo_middleware import http_proxy_to_wsgi
import osprofiler.web
import pecan

from mistral.api import access_control
from mistral.api.hooks import maintenance
from mistral.api.hooks import request_body
from mistral import config as m_config
from mistral import context as ctx
from mistral.rpc import base as rpc
from mistral.services import periodic

LOG = logging.getLogger(__name__)

HEALTHCHECK_PATH = '/healthcheck'


def _mount_healthcheck(app):
    """Route only /healthcheck to the oslo.middleware healthcheck.

    Recent oslo.middleware versions dropped the internal path match from
    the Healthcheck *middleware*: wrapped around the whole application it
    answers every request with a 200 (a 0-byte health response), so a
    request to a non-existent resource returns 200 instead of 404. The
    healthcheck is meant to be mounted at its own path now, so we dispatch
    on the path ourselves and send everything except /healthcheck straight
    to the real application.
    See lp-2163387
    """
    hc = healthcheck.Healthcheck(app, cfg.CONF)

    def dispatch(environ, start_response):
        if environ.get('PATH_INFO', '') == HEALTHCHECK_PATH:
            return hc(environ, start_response)

        return app(environ, start_response)

    return dispatch


def get_pecan_config():
    # Set up the pecan configuration.
    opts = cfg.CONF.pecan

    cfg_dict = {
        "app": {
            "root": opts.root,
            "modules": opts.modules,
            "debug": opts.debug,
            "auth_enable": opts.auth_enable,
            "guess_content_type_from_ext": False,
        }
    }

    return pecan.configuration.conf_from_dict(cfg_dict)


def setup_app(config=None):
    if not config:
        config = get_pecan_config()

    m_config.set_config_defaults()

    app_conf = dict(config.app)

    # Cron triggers can alternatively be processed by a dedicated
    # periodic server (mistral-server --server periodic), in which
    # case [cron_trigger] run_in_api should be set to False here.
    if cfg.CONF.cron_trigger.enabled and cfg.CONF.cron_trigger.run_in_api:
        LOG.warning(
            "Processing cron triggers in the API service is deprecated "
            "and will be removed in the next cycle. Deploy a dedicated "
            "periodic server (mistral-server --server periodic) and set "
            "[cron_trigger] run_in_api = False instead."
        )
        periodic.setup()

    app = pecan.make_app(
        app_conf.pop('root'),
        hooks=lambda: [request_body.RejectXMLHook(),
                       ctx.AuthHook(), maintenance.MaintenanceHook(),
                       ctx.ContextHook()],
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

    # Create HTTPProxyToWSGI wrapper
    app = http_proxy_to_wsgi.HTTPProxyToWSGI(app, cfg.CONF)

    # Create a healthcheck wrapper (only answering on /healthcheck).
    if cfg.CONF.healthcheck.enabled:
        app = _mount_healthcheck(app)

    # Create a CORS wrapper, and attach mistral-specific defaults that must be
    # included in all CORS responses.
    return cors_middleware.CORS(app, cfg.CONF)


def init_wsgi():
    # By default, oslo.config parses the CLI args if no args is provided.
    # As a result, invoking this wsgi script from gunicorn leads to the error
    # with argparse complaining that the CLI options have already been parsed.
    m_config.parse_args(args=[])

    # Configure logging: unlike the mistral-server launcher, the WSGI entry
    # point (mistral.wsgi:application, run under uWSGI/gunicorn) has to set
    # up oslo.log itself. Without this the application logs fall back to
    # Python's default handler, which drops everything below WARNING - so
    # the INFO-level API logs never show up.
    logging.setup(cfg.CONF, 'Mistral')

    return setup_app()
