# Copyright 2020 Nokia Software.
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

import collections

from oslo_config import cfg
from oslo_log import log as logging


from mistral_lib import actions as ml_actions
from mistral_lib.utils import inspect_utils as i_utils


CONF = cfg.CONF

LOG = logging.getLogger(__name__)


def _build_action_descriptor(name, action_cls):
    action_cls_attrs = i_utils.get_public_fields(action_cls)

    return ml_actions.PythonActionDescriptor(
        name,
        action_cls,
        action_cls_attrs
    )


class TestActionProvider(ml_actions.ActionProvider):
    """Action provider for tests.

    It allows to register python actions with a direct call.
    """

    def __init__(self, name='test'):
        super().__init__(name)

        self._action_descs = collections.OrderedDict()

    def register_python_action(self, action_name, action_cls):
        self._action_descs[action_name] = _build_action_descriptor(
            action_name,
            action_cls
        )

    def cleanup(self):
        self._action_descs.clear()

    def find(self, action_name, namespace=None):
        return self._action_descs.get(action_name)

    def find_all(self, namespace=None, limit=None, sort_fields=None,
                 sort_dirs=None, **filters):
        # TODO(rakhmerov): Apply sort_keys, sort_dirs, and filters.
        return self._action_descs.values()
