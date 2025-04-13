# Copyright 2018 - Extreme Networks, Inc.
# Modified in 2025 by NetCracker Technology Corp.
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

from http import HTTPStatus
import json
from oslo_config import cfg
from oslo_log import log as logging
import requests

from mistral.notifiers import base
from mistral.services import secure_request


LOG = logging.getLogger(__name__)


class WebhookPublisher(base.NotificationPublisher):

    def publish(self, ctx, ex_id, data, event, timestamp, **kwargs):
        url = kwargs.get('url')
        headers = kwargs.get('headers', {})

        if 'headers' in data:
            headers.update(data['headers'])
            del data['headers']

        if cfg.CONF.oauth2.security_profile == 'prod':
            headers = secure_request.set_auth_token(headers)

        resp = requests.post(url, data=json.dumps(data), headers=headers)

        LOG.info("Webook request url=%s code=%s", url, resp.status_code)

        if resp.status_code not in [HTTPStatus.OK, HTTPStatus.CREATED]:
            raise Exception(resp.text)
