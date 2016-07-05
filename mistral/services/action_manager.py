# Copyright 2014 - Mirantis, Inc.
# Copyright 2014 - StackStorm, Inc.
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

import inspect

from oslo_log import log as logging
from stevedore import extension

from mistral.actions import action_factory
from mistral.actions import generator_factory
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.services import actions
from mistral import utils
from mistral.utils import inspect_utils as i_utils


# TODO(rakhmerov): Make methods more consistent and granular.

LOG = logging.getLogger(__name__)

ACTIONS_PATH = 'resources/actions'
_ACTION_CTX_PARAM = 'action_context'


# TODO(rakhmerov): It's confusing because we have std.xxx actions and actions
# TODO(rakhmerov): under '../resources/actions' that we also call standard.
def register_standard_actions():
    action_paths = utils.get_file_list(ACTIONS_PATH)

    for action_path in action_paths:
        action_definition = open(action_path).read()
        actions.create_or_update_actions(
            action_definition,
            scope='public'
        )


def get_registered_actions(**kwargs):
    return db_api.get_action_definitions(**kwargs)


def register_action_class(name, action_class_str, attributes,
                          description=None, input_str=None):
    values = {
        'name': name,
        'action_class': action_class_str,
        'attributes': attributes,
        'description': description,
        'input': input_str,
        'is_system': True,
        'scope': 'public'
    }

    try:
        LOG.debug("Registering action in DB: %s" % name)

        db_api.create_action_definition(values)
    except exc.DBDuplicateEntryError:
        LOG.debug("Action %s already exists in DB." % name)


def _clear_system_action_db():
    db_api.delete_action_definitions(is_system=True)


def sync_db():
    with db_api.transaction():
        _clear_system_action_db()
        register_action_classes()
        register_standard_actions()


def _register_dynamic_action_classes():
    for generator in generator_factory.all_generators():
        actions = generator.create_actions()

        module = generator.base_action_class.__module__
        class_name = generator.base_action_class.__name__

        action_class_str = "%s.%s" % (module, class_name)

        for action in actions:
            attrs = i_utils.get_public_fields(action['class'])

            register_action_class(
                action['name'],
                action_class_str,
                attrs,
                action['description'],
                action['arg_list']
            )


def register_action_classes():
    mgr = extension.ExtensionManager(
        namespace='mistral.actions',
        invoke_on_load=False
    )
    for name in mgr.names():
        action_class_str = mgr[name].entry_point_target.replace(':', '.')
        action_class = mgr[name].plugin
        description = i_utils.get_docstring(action_class)
        input_str = i_utils.get_arg_list_as_str(action_class.__init__)

        attrs = i_utils.get_public_fields(mgr[name].plugin)

        register_action_class(
            name,
            action_class_str,
            attrs,
            description=description,
            input_str=input_str
        )

    _register_dynamic_action_classes()


def get_action_db(action_name):
    return db_api.load_action_definition(action_name)


def get_action_class(action_full_name):
    """Finds action class by full action name (i.e. 'namespace.action_name').

    :param action_full_name: Full action name (that includes namespace).
    :return: Action class or None if not found.
    """
    action_db = get_action_db(action_full_name)

    if action_db:
        return action_factory.construct_action_class(
            action_db.action_class,
            action_db.attributes
        )


def get_action_context(task_ex, action_ex_id, save=True):
    if task_ex:
        return {
            _ACTION_CTX_PARAM: {
                'workflow_name': task_ex.workflow_name,
                'workflow_execution_id': task_ex.workflow_execution_id,
                'task_id': task_ex.id,
                'task_name': task_ex.name,
                'task_tags': task_ex.tags,
                'action_execution_id': action_ex_id,
                'callback_url': '/v2/action_executions/%s' % action_ex_id
            }
        }
    elif save:
        return {
            _ACTION_CTX_PARAM: {
                'workflow_name': None,
                'workflow_execution_id': None,
                'task_id': None,
                'task_name': None,
                'task_tags': None,
                'action_execution_id': action_ex_id,
                'callback_url': '/v2/action_executions/%s' % action_ex_id
            }
        }

    return {
        _ACTION_CTX_PARAM: {
            'workflow_name': None,
            'workflow_execution_id': None,
            'task_id': None,
            'task_name': None,
            'task_tags': None,
            'action_execution_id': None,
            'callback_url': None
        }
    }


def get_empty_action_context():
    return {
        _ACTION_CTX_PARAM: {}
    }


def _has_argument(action, attributes, argument_name):
    action_cls = action_factory.construct_action_class(action, attributes)
    arg_spec = inspect.getargspec(action_cls.__init__)

    return argument_name in arg_spec.args


def has_action_context(action, attributes):
    return _has_argument(action, attributes, _ACTION_CTX_PARAM)
