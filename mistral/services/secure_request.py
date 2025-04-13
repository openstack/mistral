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
import time

import eventlet
from oslo_config import cfg
from oslo_log import log
import requests

"""
Encapsulates a raw authentication token from IDP.
Provides helper methods for extracting useful values from that token.
"""

# gap, in seconds, to determine whether the given token is about to expire
STALE_TOKEN_DURATION = 30
TOKEN = {
    "access_token": "",
    "token_type": "",
    "expires_in": "",
    "expires_at": ""
}

LOG = log.getLogger(__name__)


def request_with_retry(url, method='GET', body=None):
    retry_limit = cfg.CONF.multitenancy.dbaas_request_retry_limit
    retry_interval = cfg.CONF.multitenancy.dbaas_request_retry_interval

    do_retry = True
    retry_count = 0
    resp = None
    while do_retry and retry_count < retry_limit:
        try:
            resp = _request(url, method, body)
        except Exception as e:
            LOG.warning('Warning! couldn\'t request %s, '
                        'retrying %s of %s... \n exception: %s',
                        url, retry_count + 1, retry_limit, e)
            do_retry = True
            eventlet.sleep(retry_interval)
            retry_count = retry_count + 1
            continue

        if resp.ok:
            do_retry = False
        else:
            LOG.warning('Warning! couldn\'t request %s. '
                        'retrying %s of %s... \n return code was: %s',
                        url, retry_count + 1, retry_limit,
                        resp.status_code)
            do_retry = True
            eventlet.sleep(retry_interval)
            retry_count = retry_count + 1
    return resp


def set_auth_token(headers):
    headers = headers or {}

    if __will_expire_soon():
        __refresh()

    headers['Authorization'] = 'Bearer ' + TOKEN.get('access_token', '')
    return headers


def _request(url, method='GET', body=None):
    if cfg.CONF.pecan.auth_enable:
        return _request_with_auth(url, method=method, json=body)

    res = requests.request(url=url, method=method, json=body)
    res.raise_for_status()

    return res


def _request_with_auth(url, method, json=None, headers=None, auth_token=None,
                       **kwargs):
    """Method is used for security outcome requests

    :param auth_token:
    :param headers:
    :param json:
    :param url:
    :param method:
    :param kwargs:
    :return:
    """

    if not headers:
        headers = {"Content-Type": "application/json"}

    if not auth_token:
        if __will_expire_soon():
            __refresh()
        headers['Authorization'] = 'Bearer ' + TOKEN.get('access_token', '')
    else:
        headers['Authorization'] = 'Bearer ' + auth_token

    kwargs['headers'] = headers
    kwargs['json'] = json

    LOG.debug("Sending secure request: method=%s, url=%s, args=%s",
              method, url, kwargs)
    resp = requests.request(method=method, url=url, **kwargs)

    if resp.status_code == 401:
        __refresh()
        headers['Authorization'] = 'Bearer ' + TOKEN.get('access_token', '')
        kwargs['headers'] = headers
        LOG.debug("Sending secure request: method=%s, url=%s, args=%s",
                  method, url, kwargs)
        resp = requests.request(method=method, url=url, **kwargs)
    return resp


def __refresh():
    """Getting token from IDP and save it to the cache

    :return:
    """
    auth_type = cfg.CONF.auth_type
    if auth_type == 'mitreid':
        resp_json = _auth_using_mitreid()
    elif auth_type == 'keycloak-oidc':
        resp_json = _auth_using_keycloak()
    else:
        raise ValueError("Auth type {} doesn't support".format(auth_type))

    TOKEN['access_token'] = resp_json.get('access_token', '')
    TOKEN['token_type'] = resp_json.get('token_type', '')
    TOKEN['expires_in'] = resp_json.get('expires_in', '')
    TOKEN['expires_at'] = time.time() + TOKEN.get('expires_in', 0)


def _auth_using_keycloak():
    idp_client = base64.b64encode((cfg.CONF.oauth2.client_id + ':' +
                                   cfg.CONF.oauth2.client_secret).encode())
    realm = 'cloud-common'  # Default m2m tenant
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + idp_client.decode("utf-8"),
        'Accept': 'application/json'
    }
    data = {'grant_type': 'client_credentials'}
    idp_auth_url = cfg.CONF.oauth2.idp_url + "/auth/realms/" + realm + \
        "/protocol/openid-connect/token"

    LOG.debug("Auth request on %s with data: %s, headers: %s",
              idp_auth_url, data, headers)

    resp = requests.request('POST',
                            idp_auth_url,
                            data=data,
                            headers=headers)
    LOG.debug("Auth response: %s ", resp)

    resp.raise_for_status()

    return resp.json()


def _auth_using_mitreid():
    idp_client = base64.b64encode((cfg.CONF.oauth2.client_id + ':' +
                                   cfg.CONF.oauth2.client_secret).encode())
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic ' + idp_client.decode("utf-8"),
        'Accept': 'application/json'
    }
    data = {'grant_type': 'client_credentials'}
    resp = requests.request('POST',
                            cfg.CONF.oauth2.idp_url + '/token',
                            data=data,
                            headers=headers)
    resp.raise_for_status()
    return resp.json()


def __will_expire_soon(stale_duration=None):
    """Determine if expiration is about to occur or token is absent.

    :returns: true if expiration is within the given duration
    :rtype: boolean
    """
    stale_duration = (STALE_TOKEN_DURATION if stale_duration is None
                      else stale_duration)
    access_token = TOKEN.get('access_token')
    return not access_token or (
        time.time() > TOKEN.get('expires_at', 0) - stale_duration)
