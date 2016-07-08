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

from oslo_config import cfg
from oslo_log import log as logging
import pkg_resources as pkg

from mistral.actions import action_generator
from mistral.utils import inspect_utils as i_u
from mistral import version

os_actions_mapping_path = cfg.StrOpt('openstack_actions_mapping_path',
                                     default='actions/openstack/mapping.json')


CONF = cfg.CONF
CONF.register_opt(os_actions_mapping_path)
LOG = logging.getLogger(__name__)
MAPPING_PATH = CONF.openstack_actions_mapping_path


def get_mapping():
    def delete_comment(map_part):
        for key, value in map_part.items():
            if isinstance(value, dict):
                delete_comment(value)
        if '_comment' in map_part:
            del map_part['_comment']

    mapping = json.loads(open(pkg.resource_filename(
                         version.version_info.package,
                         MAPPING_PATH)).read())

    for k, v in mapping.items():
        if isinstance(v, dict):
            delete_comment(v)

    return mapping


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

        action_class = type(str(method_name), (cls.base_action_class,),
                            {'client_method_name': method_name})

        return action_class

    @classmethod
    def create_actions(cls):
        mapping = get_mapping()
        method_dict = mapping[cls.action_namespace]

        action_classes = []

        for action_name, method_name in method_dict.items():
            clazz = cls.create_action_class(method_name)

            try:
                client_method = clazz.get_fake_client_method()
            except Exception as e:
                LOG.warning("Failed to create action: %s.%s %s" %
                            (cls.action_namespace, action_name, e))
                client_method = None

            if client_method:
                arg_list = i_u.get_arg_list_as_str(client_method)
                description = i_u.get_docstring(client_method)
            else:
                arg_list = ''
                description = None

            action_classes.append(
                {
                    'class': clazz,
                    'name': "%s.%s" % (cls.action_namespace, action_name),
                    'description': description,
                    'arg_list': arg_list,
                }
            )

        return action_classes
