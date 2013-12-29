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

from demo_app import version


api_opts = [
    cfg.StrOpt('host', default='0.0.0.0', help='Demo-app API server host'),
    cfg.IntOpt('port', default=8988, help='Demo-app API server port')
]

CONF = cfg.CONF
CONF.register_opts(api_opts, group='api')


def parse_args(args=None, usage=None, default_config_files=None):
    CONF(args=args,
         project='mistral-demo',
         version=version,
         usage=usage,
         default_config_files=default_config_files)
