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

from oslo_config import cfg
from oslo_log import log as logging

from mistral_lib import actions as ml_actions
from mistral_lib.actions.providers import base as action_providers_base
from mistral_lib import serialization
from mistral_lib import utils

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral import expressions as expr
from mistral.lang import parser as spec_parser
from mistral.services import actions as action_service
from mistral.workflow import data_flow


CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class AdHocAction(ml_actions.Action):
    def __init__(self, base_action):
        super(AdHocAction, self).__init__()

        assert base_action is not None

        self._base_action = base_action

    def run(self, context):
        # Just run the base action. Note that the result of the base
        # action gets converted by the corresponding "post_process_result"
        # method of the ad-hoc action descriptor. It allows to implement
        # asynchronous execution model when a result of the base
        # action is delivered by a 3rd party and then it gets converted
        # after it comes to Mistral engine.
        result = self._base_action.run(context)

        if not self.is_sync():
            return None

        if not isinstance(result, ml_actions.Result):
            result = ml_actions.Result(data=result)

        return result

    @property
    def base_action(self):
        return self._base_action

    def is_sync(self):
        return self._base_action.is_sync()

    @classmethod
    def get_serialization_key(cls):
        return '%s.%s' % (AdHocAction.__module__, AdHocAction.__name__)


class AdHocActionSerializer(serialization.DictBasedSerializer):
    def serialize_to_dict(self, entity):
        p_serializer = serialization.get_polymorphic_serializer()

        return {
            'base_action': p_serializer.serialize(entity.base_action)
        }

    def deserialize_from_dict(self, entity_dict):
        p_serializer = serialization.get_polymorphic_serializer()

        return AdHocAction(
            p_serializer.deserialize(entity_dict['base_action'])
        )


serialization.register_serializer(AdHocAction, AdHocActionSerializer())


class AdHocActionDescriptor(action_providers_base.ActionDescriptorBase):
    def __init__(self, action_def):
        super(AdHocActionDescriptor, self).__init__(
            action_def.name,
            action_def.description,
            action_def.input or '',
            action_def.namespace,
            action_def.project_id,
            action_def.scope
        )

        self._definition = action_def.definition
        self._spec = spec_parser.get_action_spec(action_def.spec)
        self._action_def = action_def

    @property
    def id(self):
        return self._action_def.id

    @property
    def created_at(self):
        return self._action_def.created_at

    @property
    def updated_at(self):
        return self._action_def.updated_at

    @property
    def tags(self):
        return self._action_def.tags

    @property
    def definition(self):
        return self._definition

    @property
    def action_class_name(self):
        return "{}.{}".format(AdHocAction.__module__, AdHocAction.__name__)

    @property
    def spec(self):
        return self._spec

    def __repr__(self):
        return 'AdHoc action [name=%s, definition=%s]' % (
            self.name,
            self._definition
        )

    def _visit_hierarchy(self, callback):
        callback_result = callback(self, None)

        action_spec = self.spec

        visited = {self.name}

        while action_spec:
            base_name = action_spec.get_base()

            if base_name in visited:
                raise ValueError(
                    'Found a cycle in an ad-hoc action chain '
                    '[action_name=%s, duplicate_action_name=%s]'
                    % (self.name, base_name)
                )

            visited.add(base_name)

            system_provider = action_service.get_system_action_provider()

            base_action_desc = system_provider.find(
                base_name,
                self.namespace
            )

            if base_action_desc is None:
                raise exc.InvalidActionException(
                    "Failed to find base action [action_name=%s namespace=%s] "
                    % (base_name, self.namespace)
                )

            # For every ad-hoc action in the hierarchy invoke the callback.
            callback_result = callback(base_action_desc, callback_result)

            if isinstance(base_action_desc, AdHocActionDescriptor):
                action_spec = base_action_desc.spec
            else:
                action_spec = None

        return callback_result

    def instantiate(self, input_dict, wf_ctx):
        def _on_visit(action_desc, prev_res):
            if action_desc is self:
                base_action_desc = None
                base_input_dict = input_dict
            else:
                base_action_desc = action_desc
                base_input_dict = prev_res[1]

            if not isinstance(action_desc, AdHocActionDescriptor):
                return base_action_desc, base_input_dict

            for k, v in action_desc.spec.get_input().items():
                if (k not in base_input_dict or
                        base_input_dict[k] is utils.NotDefined):
                    base_input_dict[k] = v

            ctx = data_flow.ContextView(base_input_dict, wf_ctx)

            base_input_dict = expr.evaluate_recursively(
                action_desc.spec.get_base_input(),
                ctx
            )

            return base_action_desc, base_input_dict

        base_desc, base_input = self._visit_hierarchy(_on_visit)

        base_action = base_desc.instantiate(base_input, wf_ctx)

        return AdHocAction(base_action)

    def post_process_result(self, result):
        output_transformers = []

        def _on_visit(action_desc, prev_res):
            if isinstance(action_desc, AdHocActionDescriptor):
                output_transformers.append(action_desc.spec.get_output())

        self._visit_hierarchy(_on_visit)

        for transformer_expr in reversed(output_transformers):
            if transformer_expr is not None:
                result = ml_actions.Result(
                    data=expr.evaluate_recursively(
                        transformer_expr,
                        result.data
                    ),
                    error=result.error
                )

        return result


class AdHocActionProvider(ml_actions.ActionProvider):
    """Provides ad-hoc actions."""

    def __init__(self, name='adhoc'):
        super().__init__(name)

    def find(self, action_name, namespace=None):
        action_def = db_api.load_action_definition(
            action_name,
            namespace=namespace
        )

        if action_def is None:
            return None

        return AdHocActionDescriptor(action_def)

    def find_all(self, namespace=None, limit=None, sort_fields=None,
                 sort_dirs=None, **filters):
        # TODO(rakhmerov): Apply sort_keys, sort_dirs and filters.
        return [
            AdHocActionDescriptor(a_d)
            for a_d in db_api.get_action_definitions()
        ]
