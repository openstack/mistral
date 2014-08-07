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

import json

from oslo.config import cfg
import pkg_resources as pkg

from mistral.actions import action_generator
from mistral import version

os_actions_mapping_path = cfg.StrOpt('openstack_actions_mapping_path',
                                     default='actions/openstack/mapping.json')


CONF = cfg.CONF
CONF.register_opt(os_actions_mapping_path)
MAPPING_PATH = CONF.openstack_actions_mapping_path


class OpenStackActionGenerator(action_generator.ActionGenerator):
    """OpenStackActionGenerator.

    Base generator for all OpenStack actions,
    creates a client method declaration using
    specific python-client and sets needed arguments
    to actions.
    """
    action_namespace = None
    base_action_class = None

    @classmethod
    def create_action_class(cls, method_name):
        if not method_name:
            return None

        action_class = type(str(method_name), (cls.base_action_class,), {})
        setattr(action_class, 'client_method', method_name)

        return action_class

    @classmethod
    def create_action_classes(cls):
        mapping = json.loads(open(pkg.resource_filename(
                             version.version_info.package,
                             MAPPING_PATH)).read())
        method_dict = mapping[cls.action_namespace]

        action_classes = {}

        for action_name, method_name in method_dict.items():
            action_classes[action_name] = cls.create_action_class(method_name)

        return action_classes
