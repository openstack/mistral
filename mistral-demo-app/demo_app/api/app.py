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

import pecan


app = {
    'root': 'demo_app.api.controllers.root.RootController',
    'modules': ['demo_app.api'],
    'debug': True,
}


def get_pecan_config():
    # Set up the pecan configuration
    return pecan.configuration.conf_from_dict(app)


def setup_app(config=None):
    if not config:
        config = get_pecan_config()

    app_conf = dict(config)

    return pecan.make_app(
        app_conf.pop('root'),
        logging=getattr(config, 'logging', {}),
        **app_conf
    )
