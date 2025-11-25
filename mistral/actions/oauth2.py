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

from oslo_config import cfg

from mistral.actions import std_actions
from mistral.services import secure_request


class HTTPAction(std_actions.HTTPAction):

    def run(self, context):
        if cfg.CONF.oauth2.security_profile == 'prod':
            self.headers = secure_request.set_auth_token(self.headers or {})

        return super(HTTPAction, self).run(context)


class MistralHTTPAction(std_actions.MistralHTTPAction):

    def run(self, context):
        if cfg.CONF.oauth2.security_profile == 'prod':
            self.headers = secure_request.set_auth_token(self.headers or {})

        return super(MistralHTTPAction, self).run(context)
