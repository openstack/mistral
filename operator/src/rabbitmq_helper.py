"""
Module to handle all the kubernetes operations
"""

import logging
import requests
from requests import auth

from mistral_constants import DEFAULT_VHOST

LOG = logging.getLogger(__name__)


class RabbitMQHelper(object):
    def __init__(self, rabbit_host, rabbit_vhost, rabbit_user, rabbit_password, admin_user,
                 admin_password, queue_name_prefix):
        self._host = rabbit_host
        self._vhost = rabbit_vhost
        self._user = rabbit_user
        self._password = rabbit_password
        self._admin_user = admin_user
        self._admin_password = admin_password
        self._queue_name_prefix = queue_name_prefix

    def create_rabbit_vhost(self):
        if self._vhost == DEFAULT_VHOST:
            LOG.info('Default vhost is used. Skip a vhost creation')
            return

        res = self.request(
            "vhosts/{vhost}".format(vhost=self._vhost)
        )
        res.raise_for_status()
        LOG.info('Created {} rabbit vhost'.format(self._vhost))

    def create_rabbit_user(self):
        if self._admin_user == self._user:
            LOG.info('Admin user equals user. Skip a user creation')
            return

        body = {
            'password': self._password,
            'tags': ''
        }
        res = self.request(
            url='users/' + self._user,
            json=body
        )
        res.raise_for_status()
        LOG.info('Created {} rabbit user'.format(self._user))

    def add_rabbit_permissions(self):
        if self._vhost == DEFAULT_VHOST and self._user == self._admin_user:
            LOG.info('Default user and vhost are used. Skip a set permissions')
            return

        vhost = '%2f' if self._vhost == DEFAULT_VHOST else self._vhost
        body = {
            "configure": ".*", "write": ".*", "read": ".*"
        }
        res = self.request(
            url='permissions/{vhost}/{user}'.format(
                vhost=vhost, user=self._user),
            json=body
        )
        res.raise_for_status()
        LOG.info(
            'Add {} permissions to {} vhost'.format(self._user, vhost))

    def delete_existing_queues(self):
        vhost = '%2f' if self._vhost == DEFAULT_VHOST else self._vhost
        res = self.request(
            url='queues/{vhost}'.format(vhost=vhost),
            method='GET'
        )

        res.raise_for_status()

        queues_to_delete = []

        LOG.info(
            "Searching for existing mistral "
            "queues in {} vhost with {} prefix".format(
                vhost, self._queue_name_prefix
            )
        )

        def _is_mistral_queue(name):
            if not name.startswith(self._queue_name_prefix):
                return False
            if 'mistral' not in name:
                return False
            return True

        for queue in res.json():
            if _is_mistral_queue(queue['name']):
                queues_to_delete.append(queue['name'])

        if not queues_to_delete:
            LOG.info('There are no queues to delete.')

            LOG.info('Delete openstack exchange')

            res = self.request(
                url='exchanges/{vhost}/openstack'.format(
                    vhost=vhost
                ),
                method='DELETE'
            )

            return

        LOG.info('Founded queues to delete: {}'.format(str(queues_to_delete)))

        for queue in queues_to_delete:
            res = self.request(
                url='queues/{vhost}/{name}'.format(
                    vhost=vhost, name=queue
                ),
                method='DELETE'
            )
            res.raise_for_status()

        LOG.info('Queues were deleted.')

        LOG.info('Delete openstack exchange')

        res = self.request(
            url='exchanges/{vhost}/openstack'.format(
                vhost=vhost
            ),
            method='DELETE'
        )

    def request(self, url, method='PUT', json=None):
        res = requests.request(
            url='http://' + self._host + ':15672/api/' + url,
            method=method,
            auth=auth.HTTPBasicAuth(self._admin_user, self._admin_password),
            json=json)

        return res
