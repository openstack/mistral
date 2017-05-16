# Copyright 2016 - Brocade Communications Systems, Inc.
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

from oslo_config import cfg

from mistral import auth
from mistral import exceptions as exc


CONF = cfg.CONF


class KeystoneAuthHandler(auth.AuthHandler):

    def authenticate(self, req):
        # Note(nmakhotkin): Since we have deferred authentication,
        # need to check for auth manually (check for corresponding
        # headers according to keystonemiddleware docs.
        identity_status = req.headers.get('X-Identity-Status')
        service_identity_status = req.headers.get('X-Service-Identity-Status')

        if (identity_status == 'Confirmed' or
                service_identity_status == 'Confirmed'):
            return

        if req.headers.get('X-Auth-Token'):
            msg = 'Auth token is invalid: %s' % req.headers['X-Auth-Token']
        else:
            msg = 'Authentication required'

        raise exc.UnauthorizedException(msg)
