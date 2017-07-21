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
import os

from oslo_config import cfg
from oslo_log import log as logging
import pkg_resources as pkg

from mistral.actions import action_generator
from mistral.utils import inspect_utils as i_u
from mistral import version

CONF = cfg.CONF

LOG = logging.getLogger(__name__)


def get_mapping():
    def delete_comment(map_part):
        for key, value in map_part.items():
            if isinstance(value, dict):
                delete_comment(value)
        if '_comment' in map_part:
            del map_part['_comment']
    package = version.version_info.package

    if os.path.isabs(CONF.openstack_actions_mapping_path):
        mapping_file_path = CONF.openstack_actions_mapping_path
    else:
        path = CONF.openstack_actions_mapping_path
        mapping_file_path = pkg.resource_filename(package, path)

    LOG.info(
        "Processing OpenStack action mapping from file: %s",
        mapping_file_path
    )

    with open(mapping_file_path) as fh:
        mapping = json.load(fh)

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
    def prepare_action_inputs(cls, origin_inputs, added=[]):
        """Modify action input string.

        Sometimes we need to change the default action input definition for
        OpenStack actions in order to make the workflow more powerful.

        Examples::

            >>> prepare_action_inputs('a,b,c', added=['region=RegionOne'])
            a, b, c, region=RegionOne
            >>> prepare_action_inputs('a,b,c=1', added=['region=RegionOne'])
            a, b, region=RegionOne, c=1
            >>> prepare_action_inputs('a,b,c=1,**kwargs',
                                      added=['region=RegionOne'])
            a, b, region=RegionOne, c=1, **kwargs
            >>> prepare_action_inputs('**kwargs', added=['region=RegionOne'])
            region=RegionOne, **kwargs
            >>> prepare_action_inputs('', added=['region=RegionOne'])
            region=RegionOne

        :param origin_inputs: A string consists of action inputs, separated by
            comma.
        :param added: (Optional) A list of params to add to input string.
        :return: The new action input string.
        """
        if not origin_inputs:
            return ", ".join(added)

        inputs = [i.strip() for i in origin_inputs.split(',')]
        kwarg_index = None

        for index, input in enumerate(inputs):
            if "=" in input:
                kwarg_index = index
            if "**" in input:
                kwarg_index = index - 1

        kwarg_index = len(inputs) if kwarg_index is None else kwarg_index
        kwarg_index = kwarg_index + 1 if kwarg_index < 0 else kwarg_index

        for a in added:
            if "=" not in a:
                inputs.insert(0, a)
                kwarg_index += 1
            else:
                inputs.insert(kwarg_index, a)

        return ", ".join(inputs)

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
        method_dict = mapping.get(cls.action_namespace, {})

        action_classes = []

        for action_name, method_name in method_dict.items():
            class_ = cls.create_action_class(method_name)

            try:
                client_method = class_.get_fake_client_method()
            except Exception:
                LOG.exception(
                    "Failed to create action: %s.%s",
                    cls.action_namespace, action_name
                )
                continue

            arg_list = i_u.get_arg_list_as_str(client_method)

            # Support specifying region for OpenStack actions.
            modules = CONF.openstack_actions.modules_support_region
            if cls.action_namespace in modules:
                arg_list = cls.prepare_action_inputs(
                    arg_list,
                    added=['action_region=""']
                )

            description = i_u.get_docstring(client_method)

            action_classes.append(
                {
                    'class': class_,
                    'name': "%s.%s" % (cls.action_namespace, action_name),
                    'description': description,
                    'arg_list': arg_list,
                }
            )

        return action_classes
