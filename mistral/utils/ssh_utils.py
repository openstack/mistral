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

import paramiko

from mistral.openstack.common import log as logging


LOG = logging.getLogger(__name__)


def _read_paramimko_stream(recv_func):
    result = ''
    buf = recv_func(1024)
    while buf != '':
        result += buf
        buf = recv_func(1024)

    return result


def _connect(host, username, password):
    LOG.debug('Creating SSH connection to %s' % host)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password)
    return ssh


def _cleanup(ssh):
    ssh.close()


def execute_command(cmd, host, username, password,
                    get_stderr=False, raise_when_error=True):
    ssh = _connect(host, username, password)

    LOG.debug("Executing command %s" % cmd)

    try:
        chan = ssh.get_transport().open_session()
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
        _cleanup(ssh)
