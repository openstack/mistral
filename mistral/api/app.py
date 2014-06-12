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

from oslo.config import cfg
import pecan

from mistral.api import access_control
from mistral.api.hooks import engine
from mistral import context as ctx
from mistral.db import api as db_api
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


def setup_app(config=None, transport=None):
    if not config:
        config = get_pecan_config()

    app_conf = dict(config.app)

    db_api.setup_db()

    # TODO(akuznetsov) move this to trigger scheduling to separate process
    periodic.setup(transport)

    app = pecan.make_app(
        app_conf.pop('root'),
        hooks=lambda: [ctx.ContextHook(),
                       engine.EngineHook(transport=transport)],
        logging=getattr(config, 'logging', {}),
        **app_conf
    )

    # Set up access control.
    app = access_control.setup(app)

    return app
