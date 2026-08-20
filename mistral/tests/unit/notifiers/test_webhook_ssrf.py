# Copyright 2026 - OVHcloud.
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

import socket
from unittest import mock

from mistral import exceptions as exc
from mistral.notifiers.publishers import webhook
from mistral.tests.unit import base


class WebhookPublisherSsrfTest(base.BaseTest):
    @mock.patch('mistral.notifiers.publishers.webhook.requests.post')
    @mock.patch.object(socket, 'getaddrinfo')
    def test_publish_to_metadata_is_blocked(self, gai, post):
        gai.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, '',
             ('169.254.169.254', 80))
        ]

        pub = webhook.WebhookPublisher()

        self.assertRaises(
            exc.UrlNotAllowedException,
            pub.publish,
            {}, 'ex-id', {'a': 1}, 'event', 'ts',
            url='http://169.254.169.254/'
        )

        # The request must never be issued.
        post.assert_not_called()
