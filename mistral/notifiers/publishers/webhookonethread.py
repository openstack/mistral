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

from eventlet.semaphore import Semaphore
from eventlet import sleep as eventlet_sleep
import json
from oslo_config import cfg
import requests
from six.moves import http_client

from oslo_log import log as logging

from mistral.notifiers import base
from mistral.services import secure_request


LOG = logging.getLogger(__name__)


class WebhookOneThreadPublisher(base.NotificationPublisher):
    def __init__(self):
        self._sem = Semaphore()

    def publish(self, ctx, ex_id, data, event, timestamp, **kwargs):
        with self._sem:
            url = kwargs.get('url')
            headers = kwargs.get('headers', {})
            number_of_retries = int(kwargs.get('number_of_retries', 3))
            polling_time = int(kwargs.get('polling_time', 10))
            first_attempt = True

            LOG.info(
                "Webhook: [event=%s, ex_id=%s, url=%s, number_of_retries=%s,"
                " polling_time=%s]", event, ex_id, url,
                number_of_retries, polling_time
            )

            unlim = False
            if number_of_retries == -1:
                unlim = True

            retry_count = 1
            while first_attempt or unlim or retry_count <= number_of_retries:
                first_attempt = False
                try:
                    if cfg.CONF.oauth2.security_profile == 'prod':
                        headers = secure_request.set_auth_token(headers)

                    resp = requests.post(
                        url,
                        data=json.dumps(data),
                        headers=headers
                    )

                    if resp.status_code in [http_client.OK,
                                            http_client.CREATED]:
                        LOG.info(
                            "Message delivered: "
                            "[event=%s:%s, ex_id=%s, url=%s,"
                            " number_of_retry=%s]",
                            data["name"], event, ex_id, url, retry_count
                        )
                        return
                    else:
                        LOG.error(
                            "Message not delivered: "
                            "[event=%s:%s, ex_id=%s, url=%s, status_code=%s, "
                            "text=%s, number_of_retry=%s]",
                            data["name"], event, ex_id, url, resp.status_code,
                            resp.text, retry_count
                        )
                except BaseException as e:
                    LOG.error(
                        "Message not delivered: "
                        "[event=%s:%s, ex_id=%s, url=%s, message=%s, "
                        "number_of_retry=%s]",
                        data["name"], event, ex_id, url, str(e), retry_count
                    )

                retry_count += 1
                eventlet_sleep(polling_time)

            LOG.error(
                'The number of retries is over: [url=%s, event=%s, ex_id=%s]',
                url, event, ex_id
            )
