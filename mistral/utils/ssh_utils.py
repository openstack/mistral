# -*- coding: utf-8 -*-
#
# Copyright 2014 - Mirantis, Inc.
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

from os import path

import six

from oslo_log import log as logging
import paramiko

from mistral import exceptions as exc


KEY_PATH = path.expanduser("~/.ssh/")
LOG = logging.getLogger(__name__)


def _read_paramimko_stream(recv_func):
    result = ''
    buf = recv_func(1024)
    while buf != '':
        result += buf
        buf = recv_func(1024)

    return result


def _to_paramiko_private_key(private_key_filename, password=None):
    if '../' in private_key_filename or '..\\' in private_key_filename:
        raise exc.DataAccessException(
            "Private key filename must not contain '..'. "
            "Actual: %s" % private_key_filename
        )

    private_key_path = KEY_PATH + private_key_filename

    return paramiko.RSAKey(
        filename=private_key_path,
        password=password
    )


def _connect(host, username, password=None, pkey=None, proxy=None):
    if isinstance(pkey, six.string_types):
        pkey = _to_paramiko_private_key(pkey, password)

    LOG.debug('Creating SSH connection to %s' % host)

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh_client.connect(
        host,
        username=username,
        password=password,
        pkey=pkey,
        sock=proxy
    )

    return ssh_client


def _cleanup(ssh_client):
    ssh_client.close()


def _execute_command(ssh_client, cmd, get_stderr=False,
                     raise_when_error=True):
    try:
        chan = ssh_client.get_transport().open_session()
        chan.exec_command(cmd)

        # TODO(nmakhotkin): that could hang if stderr buffer overflows
        stdout = _read_paramimko_stream(chan.recv)
        stderr = _read_paramimko_stream(chan.recv_stderr)

        ret_code = chan.recv_exit_status()

        if ret_code and raise_when_error:
            raise RuntimeError("Cmd: %s\nReturn code: %s\nstdout: %s"
                               % (cmd, ret_code, stdout))
        if get_stderr:
            return ret_code, stdout, stderr
        else:
            return ret_code, stdout
    finally:
        _cleanup(ssh_client)


def execute_command_via_gateway(cmd, host, username, private_key_filename,
                                gateway_host, gateway_username=None,
                                proxy_command=None, password=None):
    LOG.debug('Creating SSH connection')

    private_key = _to_paramiko_private_key(private_key_filename, password)

    proxy = None

    if proxy_command:
        LOG.debug('Creating proxy using command: %s' % proxy_command)

        proxy = paramiko.ProxyCommand(proxy_command)

    _proxy_ssh_client = paramiko.SSHClient()
    _proxy_ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    LOG.debug('Connecting to proxy gateway at: %s' % gateway_host)

    if not gateway_username:
        gateway_username = username

    _proxy_ssh_client.connect(
        gateway_host,
        username=gateway_username,
        pkey=private_key,
        sock=proxy
    )

    proxy = _proxy_ssh_client.get_transport().open_session()
    proxy.exec_command("nc {0} 22".format(host))

    ssh_client = _connect(
        host,
        username=username,
        pkey=private_key,
        proxy=proxy
    )

    try:
        return _execute_command(
            ssh_client,
            cmd,
            get_stderr=False,
            raise_when_error=True
        )
    finally:
        _cleanup(_proxy_ssh_client)


def execute_command(cmd, host, username, password=None,
                    private_key_filename=None, get_stderr=False,
                    raise_when_error=True):
    ssh_client = _connect(host, username, password, private_key_filename)

    LOG.debug("Executing command %s" % cmd)

    return _execute_command(ssh_client, cmd, get_stderr, raise_when_error)
