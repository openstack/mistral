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

#! /usr/bin/env python
# -*- coding: utf-8 -*-

import abc
import pprint
import re
import base64
import requests


def get_logger():
    try:
        from robot.api import logger
        return logger
    except Exception:
        from oslo_log import log as logging
        return logging.getLogger(__name__)


LOG = get_logger()


class IdpBase(abc.ABC):

    def __init__(self, idp_server, client_register_token,
                 idp_client_id, idp_client_secret, multitenancy_enabled=True):
        self._idp_server = idp_server
        self._client_register_token = client_register_token
        self._multitenancy_enabled = multitenancy_enabled
        self._idp_client_id = idp_client_id
        self._idp_client_secret = idp_client_secret

        self._session = requests.session()
        self._client_id = None

        LOG.info(f'IDP parameters: {self.__dict__}')

    @abc.abstractmethod
    def get_token(self):
        pass

    @abc.abstractmethod
    def get_multitenancy_token(self, tenant_name, username, password):
        pass


class KeycloakLibrary(IdpBase):

    def get_token(self):
        idp_client = base64.b64encode((self._idp_client_id + ':' +
                                       self._idp_client_secret).encode())
        realm = 'cloud-common'  # Default m2m tenant
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + idp_client.decode("utf-8"),
            'Accept': 'application/json'
        }
        data = {'grant_type': 'client_credentials'}
        idp_auth_url = self._idp_server + "/auth/realms/" + realm + \
                       "/protocol/openid-connect/token"

        LOG.debug("Auth request on %s with data: %s, headers: %s" % (
            idp_auth_url, data, headers))

        resp = requests.request('POST',
                                idp_auth_url,
                                data=data,
                                headers=headers)
        LOG.debug("Auth response: %s " % resp)

        resp.raise_for_status()

        return resp.json()['access_token']

    def get_multitenancy_token(self, tenant_name, username, password):
        return ""


class MitreidLibrary(IdpBase):

    def register_client(self, tenant_name):
        register_url = self._idp_server + '/register'

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Bearer ' + self._client_register_token
        }
        data = {
            "client_name": tenant_name,
            "redirect_uris": [
                self._idp_server
            ],
            "grant_types": [
                "client_credentials"
            ],
            "application_type": "web",
            "scope": "profile openid"
        }
        resp = self._session.post(register_url, json=data, headers=headers)

        resp.raise_for_status()

        resp_json = resp.json()
        LOG.debug("HTTP response: " + pprint.pformat(resp_json))

        self._client_id = resp_json['client_id']
        return resp_json['client_id'], resp_json['client_secret']

    def _login(self, tenant_name, username, password):
        login_url = self._idp_server + '/j_spring_security_check'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'tenant_id': tenant_name,
            'login': username,
            'password': password
        }
        resp = self._session.post(login_url,
                                  data=data,
                                  headers=headers)

        resp.raise_for_status()
        LOG.debug('Login: ' + str(resp.content))

    def get_token(self):
        if self._idp_client_id and self._idp_client_secret:
            client, secret = self._idp_client_id, self._idp_client_secret
        else:
            client, secret = self.register_client('test')

        input_bytes = f"{client}:{secret}".encode('utf8')
        output_bytes = base64.urlsafe_b64encode(input_bytes)
        idp_client = output_bytes.decode('ascii')

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic ' + idp_client,
            'Accept': 'application/json'
        }
        data = {'grant_type': 'client_credentials'}

        resp = requests.post(self._idp_server + '/token', data=data,
                             headers=headers, timeout=5)
        LOG.debug(resp.text)

        resp.raise_for_status()

        return resp.json()['access_token']

    def get_multitenancy_token(self, tenant_name, username, password):
        self.register_client(tenant_name)
        self._login(tenant_name, username, password)

        auth_url = self._idp_server + '/authorize'
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'redirect_uri': self._idp_server,
            'scope': 'openid profile',
            'response_type': 'token',
            'client_id': self._client_id
        }
        resp = self._session.post(auth_url,
                                  data=data,
                                  headers=headers,
                                  allow_redirects=False)
        resp.raise_for_status()

        LOG.debug("HTTP response: %s",
                  pprint.pformat(resp))
        token = re.findall(r'access_token=\S[^&]+&', resp.headers['Location'])

        return token[0][13:len(token[0]) - 1]

    def get_all_tenant(self, token):
        get_tenant_url = self._idp_server + '/security/tenants/list'
        headers = {
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/json'
        }
        resp = self._session.get(get_tenant_url,
                                 headers=headers,
                                 allow_redirects=False)
        resp.raise_for_status()

        LOG.debug("HTTP response: %s",
                  pprint.pformat(resp))

        return resp.json()

    def get_tenant(self, token, tenant_name):
        get_tenant_url = self._idp_server + '/security/tenants/' + tenant_name
        headers = {
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/json'
        }
        resp = self._session.get(get_tenant_url,
                                 headers=headers,
                                 allow_redirects=False)
        resp.raise_for_status()

        LOG.debug("HTTP response: %s",
                  pprint.pformat(resp))

        return resp.json()

    def create_tenant(self, token, tenant_name, username, password):
        create_url = self._idp_server + '/security/tenants/create'
        headers = {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        resp = self._session.post(create_url,
                                  json={
                                      "name": tenant_name,
                                      "username": username,
                                      "password": password
                                  },
                                  headers=headers,
                                  allow_redirects=False)

        resp.raise_for_status()

        LOG.debug("HTTP response: %s",
                  pprint.pformat(resp.content))

        return resp.json()['id']

    def activate_tenant(self, token, tenant_name):
        activate_tenant_url = "{}/security/tenants/activate/{}".format(
            self._idp_server, tenant_name
        )
        headers = {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        resp = self._session.post(activate_tenant_url,
                                  headers=headers,
                                  allow_redirects=False)
        resp.raise_for_status()

        LOG.debug("HTTP response: %s",
                  pprint.pformat(resp))
        LOG.debug('Activate: {}'.format(resp.content))

        return resp.json()

    def enable_tenant(self, token, tenant_name):
        enable_tenant_url = '{}/security/tenants/enable/{}'.format(
            self._idp_server, tenant_name
        )
        headers = {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        resp = self._session.post(enable_tenant_url,
                                  headers=headers,
                                  allow_redirects=False)

        print("HTTP response: %s",
              pprint.pformat(resp))
        print('Enable: {}'.format(resp.content))

        resp.raise_for_status()

        return resp.json()


def error_handler(parser, message):
    print(message)
    parser.print_help()
    exit(1)


if __name__ == '__main__':
    mitreid = MitreidLibrary(
        idp_server='http://identity-management-security-services.ci-master.openshift.sdntest.netcracker.com',
        client_register_token='qhpazpmb_mD0IbX3zzWFcevMOv8Qf03X')
    token = mitreid.get_token()
    print(token)
