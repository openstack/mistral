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

from oslo_log import log

from mistral.actions import base
from mistral import exceptions as exc

LOG = log.getLogger(__name__)


class OpenStackAction(base.Action):
    """OpenStack Action.

    OpenStack Action is the basis of all OpenStack-specific actions,
    which are constructed via OpenStack Action generators.
    """
    _kwargs_for_run = {}
    _client_class = None
    client_method_name = None

    def __init__(self, **kwargs):
        self._kwargs_for_run = kwargs

    @abc.abstractmethod
    def _get_client(self):
        """Returns python-client instance

        Gets client instance according to specific OpenStack Service
        (e.g. Nova, Glance, Heat, Keystone etc)

        """
        pass

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
        # Default is simple _client_class instance
        return cls._client_class()

    @classmethod
    def get_fake_client_method(cls):
        return cls._get_client_method(cls._get_fake_client())

    def run(self):
        try:
            method = self._get_client_method(self._get_client())

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

    def test(self):
        return dict(
            zip(self._kwargs_for_run, ['test'] * len(self._kwargs_for_run))
        )
