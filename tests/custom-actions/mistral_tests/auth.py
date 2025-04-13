# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64

import requests
from mistral_lib.actions import Action, Result
from mistral_tests.common import idp_utils


class AuthAction(Action):

    def __init__(self):
        super(AuthAction, self).__init__()

    def run(self, context):
        if idp_utils.security_profile() != "prod":
            return Result(error='Check the security profile which dosn`t '
                                'equal "prod"')

        return self.auth(idp_utils.idp_client_id(),
                         idp_utils.idp_client_secret(),
                         idp_utils.identity_provider_url())

    def auth(self, client_id, client_secret, url):
        idp_client = base64.b64encode((client_id + ':' + client_secret)
                                      .encode())
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + idp_client,
            'Accept': 'application/json'
        }
        data = {'grant_type': 'client_credentials'}
        resp = requests.request(
            'POST', url + '/token', data=data, headers=headers
        )
        resp.raise_for_status()

        return resp.json()
