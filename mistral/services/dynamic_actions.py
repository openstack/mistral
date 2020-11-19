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


from oslo_log import log as logging

from mistral.db.v2 import api as db_api


LOG = logging.getLogger(__name__)


def create_dynamic_actions(action_list, namespace=''):
    created_actions = []

    with db_api.transaction():
        for action in action_list:
            created_actions.append(
                db_api.create_dynamic_action_definition({
                    'name': action['name'],
                    'class_name': action['class_name'],
                    'namespace': namespace,
                    'code_source_id': action['code_source_id']
                })
            )

    return created_actions


def delete_dynamic_action(identifier, namespace=''):
    with db_api.transaction():
        return db_api.delete_dynamic_action_definition(
            identifier,
            namespace
        )


def get_dynamic_actions(limit=None, marker=None, sort_keys=None,
                        sort_dirs=None, fields=None, **kwargs):
    with db_api.transaction():
        return db_api.get_dynamic_action_definitions(
            limit=limit,
            marker=marker,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            **kwargs
        )


def get_dynamic_action(identifier, namespace=''):
    with db_api.transaction():
        return db_api.get_dynamic_action_definition(
            identifier,
            namespace=namespace
        )


def update_dynamic_action(identifier, values, namespace=''):
    with db_api.transaction():
        return db_api.update_dynamic_action_definition(
            identifier,
            values,
            namespace
        )


def update_dynamic_actions(actions, namespace=''):
    return [
        update_dynamic_action(name, values, namespace)
        for name, values in actions.items()
    ]
