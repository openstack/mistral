# Copyright 2015 - Mirantis, Inc.
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

import json
import os
from os import path
import time

from oslo_log import log as logging
from paramiko import ssh_exception
from tempest import config
from tempest.lib import exceptions
from tempest import test

from mistral import utils
from mistral.utils import ssh_utils
from mistral_tempest_tests.tests import base


LOG = logging.getLogger(__name__)
CONF = config.CONF
SSH_KEYS_DIRECTORY = path.expanduser("~/.ssh/")


class SSHActionsTestsV2(base.TestCaseAdvanced):

    _service = 'workflowv2'

    @classmethod
    def _create_security_group_rule_ssh(cls):
        sec_groups = (
            cls.mgr.compute_security_groups_client.
            list_security_groups()
        )
        sec_groups = sec_groups['security_groups']

        default_group = next(
            g for g in sec_groups if g['name'] == 'default'
        )

        rule = (
            cls.mgr.compute_security_group_rules_client
            .create_security_group_rule(
                parent_group_id=default_group['id'],
                ip_protocol="tcp",
                from_port=22,
                to_port=22,
                cidr="0.0.0.0/0"
            )
        )

        cls.ssh_rule_id = rule['security_group_rule']['id']

    @classmethod
    def _create_server(cls, server_name, **kwargs):
        return cls.mgr.servers_client.create_server(
            name=server_name,
            imageRef=CONF.compute.image_ref,
            flavorRef=CONF.compute.flavor_ref,
            **kwargs
        ).get('server')

    @classmethod
    def _associate_floating_ip_to_server(cls, server_id):
        fl_ip_client = cls.mgr.compute_floating_ips_client

        all_ips = fl_ip_client.list_floating_ips().get(
            'floating_ips'
        )
        free_ips = list(
            filter(lambda fl_ip: fl_ip['instance_id'] is None, all_ips)
        )

        if free_ips:
            ip = free_ips[0]['ip']
        else:
            # Allocate new floating ip.
            ip = fl_ip_client.create_floating_ip()['floating_ip']['ip']

        # Associate IP.
        fl_ip_client.associate_floating_ip_to_server(
            floating_ip=ip,
            server_id=server_id
        )

        return ip

    @classmethod
    def _wait_until_server_up(cls, server_ip, timeout=120, delay=2):
        seconds_remain = timeout

        LOG.info("Waiting server SSH [IP=%s]..." % server_ip)

        while seconds_remain > 0:
            try:
                ssh_utils.execute_command('cd', server_ip, None)
            except ssh_exception.SSHException:
                LOG.info("Server %s: SSH service is ready.")
                return
            except Exception as e:
                LOG.info(str(e))
                seconds_remain -= delay
                time.sleep(delay)
            else:
                return

        raise Exception(
            "Failed waiting until server's '%s' SSH is up." % server_ip
        )

    @classmethod
    def _wait_until_server_active(cls, server_id, timeout=60, delay=2):
        seconds_remain = timeout

        LOG.info("Waiting server [id=%s]..." % server_id)

        while seconds_remain > 0:
            server_info = cls.mgr.servers_client.show_server(server_id)
            if server_info['server']['status'] == 'ACTIVE':
                return

            seconds_remain -= delay
            time.sleep(delay)

        raise Exception(
            "Failed waiting until server %s is active." % server_id
        )

    @classmethod
    def _wait_until_server_delete(cls, server_id, timeout=60, delay=2):
        seconds_remain = timeout

        LOG.info("Deleting server [id=%s]..." % server_id)

        while seconds_remain > 0:
            try:
                cls.mgr.servers_client.show_server(server_id)
                seconds_remain -= delay
                time.sleep(delay)
            except exceptions.NotFound:
                return

        raise RuntimeError("Server delete timeout!")

    @classmethod
    def resource_setup(cls):
        super(SSHActionsTestsV2, cls).resource_setup()

        # Modify security group for accessing VM via SSH.
        cls._create_security_group_rule_ssh()

        # Create keypair (public and private keys).
        cls.private_key, cls.public_key = utils.generate_key_pair()
        cls.key_name = 'mistral-functional-tests-key'

        # If ZUUL_PROJECT is specified, it means
        # tests are running on Jenkins gate.

        if os.environ.get('ZUUL_PROJECT'):
            cls.key_dir = "/opt/stack/new/.ssh/"

            if not path.exists(cls.key_dir):
                os.mkdir(cls.key_dir)
        else:
            cls.key_dir = SSH_KEYS_DIRECTORY

        utils.save_text_to(
            cls.private_key,
            cls.key_dir + cls.key_name,
            overwrite=True
        )

        LOG.info(
            "Private key saved to %s" % cls.key_dir + cls.key_name
        )

        # Create keypair in nova.
        cls.mgr.keypairs_client.create_keypair(
            name=cls.key_name,
            public_key=cls.public_key
        )

        # Start servers and provide key_name.
        # Note: start public vm only after starting the guest one,
        # so we can track public vm launching using ssh, but can't
        # do the same with guest VM.
        cls.guest_vm = cls._create_server(
            'mistral-guest-vm',
            key_name=cls.key_name
        )
        cls.public_vm = cls._create_server(
            'mistral-public-vm',
            key_name=cls.key_name
        )

        cls._wait_until_server_active(cls.public_vm['id'])

        cls.public_vm_ip = cls._associate_floating_ip_to_server(
            cls.public_vm['id']
        )

        # Wait until server is up.
        cls._wait_until_server_up(cls.public_vm_ip)

        # Update servers info.
        cls.public_vm = cls.mgr.servers_client.show_server(
            cls.public_vm['id']
        ).get('server')

        cls.guest_vm = cls.mgr.servers_client.show_server(
            cls.guest_vm['id']
        ).get('server')

    @classmethod
    def resource_cleanup(cls):
        fl_ip_client = cls.mgr.compute_floating_ips_client
        fl_ip_client.disassociate_floating_ip_from_server(
            cls.public_vm_ip,
            cls.public_vm['id']
        )

        cls.mgr.servers_client.delete_server(cls.public_vm['id'])
        cls.mgr.servers_client.delete_server(cls.guest_vm['id'])

        cls._wait_until_server_delete(cls.public_vm['id'])
        cls._wait_until_server_delete(cls.guest_vm['id'])

        cls.mgr.keypairs_client.delete_keypair(cls.key_name)

        cls.mgr.compute_security_group_rules_client.delete_security_group_rule(
            cls.ssh_rule_id
        )
        os.remove(cls.key_dir + cls.key_name)

        super(SSHActionsTestsV2, cls).resource_cleanup()

    @test.attr(type='sanity')
    def test_run_ssh_action(self):
        input_data = {
            'cmd': 'hostname',
            'host': self.public_vm_ip,
            'username': CONF.validation.image_ssh_user,
            'private_key_filename': self.key_name
        }

        resp, body = self.client.create_action_execution(
            {
                'name': 'std.ssh',
                'input': json.dumps(input_data)
            }
        )

        self.assertEqual(201, resp.status)

        output = json.loads(body['output'])

        self.assertIn(self.public_vm['name'], output['result'])

    @test.attr(type='sanity')
    def test_run_ssh_proxied_action(self):
        guest_vm_ip = self.guest_vm['addresses'].popitem()[1][0]['addr']

        input_data = {
            'cmd': 'hostname',
            'host': guest_vm_ip,
            'username': CONF.validation.image_ssh_user,
            'private_key_filename': self.key_name,
            'gateway_host': self.public_vm_ip,
            'gateway_username': CONF.validation.image_ssh_user
        }

        resp, body = self.client.create_action_execution(
            {
                'name': 'std.ssh_proxied',
                'input': json.dumps(input_data)
            }
        )

        self.assertEqual(201, resp.status)

        output = json.loads(body['output'])

        self.assertIn(self.guest_vm['name'], output['result'])
