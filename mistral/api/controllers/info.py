# Copyright 2022 - NetCracker Technology Corp.
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

import json
from mistral import exceptions as exc
from mistral.utils import rest_utils
import os.path
from oslo_config import cfg
import pecan
from pecan import rest


class InfoController(rest.RestController):

    @rest_utils.wrap_pecan_controller_exception
    @pecan.expose('json')
    def get(self):
        if not cfg.CONF.api.enable_info_endpoint:
            raise exc.InfoEndpointNotAvailableException(
                "Info endpoint disabled."
            )
        file_path = cfg.CONF.api.info_json_file_path
        if not os.path.exists(file_path):
            raise exc.InfoEndpointNotAvailableException(
                "Incorrect path to info json file."
            )
        with open(file_path) as f:
            return json.load(f)
