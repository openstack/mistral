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

import abc
import inspect
import traceback

from cachetools import LRUCache

from oslo_log import log

from mistral import exceptions as exc
from mistral.utils.openstack import keystone as keystone_utils
from mistral_lib import actions

from threading import Lock

LOG = log.getLogger(__name__)


class OpenStackAction(actions.Action):
    """OpenStack Action.

    OpenStack Action is the basis of all OpenStack-specific actions,
    which are constructed via OpenStack Action generators.
    """
    _kwargs_for_run = {}
    client_method_name = None
    _clients = LRUCache(100)
    _lock = Lock()
    _service_name = None
    _service_type = None

    def __init__(self, **kwargs):
        self._kwargs_for_run = kwargs
        self.action_region = self._kwargs_for_run.pop('action_region', None)

    @abc.abstractmethod
    def _create_client(self):
        """Creates client required for action operation"""
        pass

    @classmethod
    def _get_client_class(cls):
        return None

    @classmethod
    def _get_client_method(cls, client):
        hierarchy_list = cls.client_method_name.split('.')
        attribute = client

        for attr in hierarchy_list:
            attribute = getattr(attribute, attr)

        return attribute

    @classmethod
    def _get_fake_client(cls):
        """Returns python-client instance which initiated via wrong args.

        It is needed for getting client-method args and description for
        saving into DB.
        """
        # Default is simple _get_client_class instance
        return cls._get_client_class()()

    @classmethod
    def get_fake_client_method(cls):
        return cls._get_client_method(cls._get_fake_client())

    def _get_client(self, context):
        """Returns python-client instance via cache or creation

        Gets client instance according to specific OpenStack Service
        (e.g. Nova, Glance, Heat, Keystone etc)

        """

        # TODO(d0ugal): Caching has caused some security problems and
        #               regressions in Mistral. It is disabled for now and
        #               will be revisited in Ocata. See:
        #               https://bugs.launchpad.net/mistral/+bug/1627689
        return self._create_client(context)

        client_class = self.__class__.__name__
        # Colon character is reserved (rfc3986) which avoids key collisions.
        key = client_class + ':' + context.project_id

        def create_cached_client():
            new_client = self._create_client(context)
            new_client._mistral_ctx_expires_at = context.expires_at

            with self._lock:
                self._clients[key] = new_client

            return new_client

        with self._lock:
            client = self._clients.get(key)

        if client is None:
            return create_cached_client()

        if keystone_utils.will_expire_soon(client._mistral_ctx_expires_at):
            LOG.debug("cache expiring soon, will refresh client")

            return create_cached_client()

        LOG.debug("cache not expiring soon, will return cached client")

        return client

    def get_service_endpoint(self):
        """Get OpenStack service endpoint.

        'service_name' and 'service_type' are defined in specific OpenStack
        service action.
        """
        endpoint = keystone_utils.get_endpoint_for_project(
            service_name=self._service_name,
            service_type=self._service_type,
            region_name=self.action_region
        )

        return endpoint

    def run(self, context):
        try:
            method = self._get_client_method(self._get_client(context))

            result = method(**self._kwargs_for_run)

            if inspect.isgenerator(result):
                return [v for v in result]

            return result
        except Exception as e:
            # Print the traceback for the last exception so that we can see
            # where the issue comes from.
            LOG.warning(traceback.format_exc())

            e_str = '%s: %s' % (type(e), e.message)

            raise exc.ActionException(
                "%s.%s failed: %s" %
                (self.__class__.__name__, self.client_method_name, e_str)
            )

    def test(self, context):
        return dict(
            zip(self._kwargs_for_run, ['test'] * len(self._kwargs_for_run))
        )
