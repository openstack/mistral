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

import datetime
from oslo_utils import timeutils
from oslo_utils import uuidutils
import pecan
import pecan.testing

from mistral.api import app as pecan_app
from mistral.tests.unit.api import base


WORKBOOKS = [
    {
        u'name': u'my_workbook',
        u'description': u'My cool Mistral workbook',
        u'scope': None,
        u'tags': [u'deployment', u'demo']
    }
]


PKI_TOKEN_VERIFIED = {
    'token': {
        'methods': ['password'],
        'roles': [{'id': uuidutils.generate_uuid(dashed=False),
                   'name': 'admin'}],
        'expires_at': datetime.datetime.isoformat(
            datetime.datetime.utcnow() + datetime.timedelta(seconds=60)
        ),
        'project': {
            'domain': {'id': 'default', 'name': 'Default'},
            'id': uuidutils.generate_uuid(dashed=False),
            'name': 'Mistral'
        },
        'catalog': [],
        'extras': {},
        'user': {
            'domain': {'id': 'default', 'name': 'Default'},
            'id': uuidutils.generate_uuid(dashed=False),
            'name': 'admin'
        },
        'issued_at': datetime.datetime.isoformat(timeutils.utcnow())
    }
}


class TestKeystoneMiddleware(base.APITest):
    """Test keystone middleware AuthProtocol.

    It checks that keystone middleware AuthProtocol is executed
    when enabled.
    """

    def setUp(self):
        super(TestKeystoneMiddleware, self).setUp()

        self.override_config('auth_enable', True, group='pecan')
        self.override_config('enabled', False, group='cron_trigger')

        self.app = pecan.testing.load_test_app(
            dict(pecan_app.get_pecan_config())
        )
