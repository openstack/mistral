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
import types

from mistral_lib import actions as ml_actions
from mistral_lib import serialization
from mistral_lib.utils import inspect_utils

from mistral.db.v2 import api as db_api

CONF = cfg.CONF


class DynamicAction(ml_actions.Action):
    def __init__(self, action, code_source_id, namespace=''):
        super(DynamicAction, self).__init__()

        self.action = action
        self.namespace = namespace
        self.code_source_id = code_source_id

    @classmethod
    def get_serialization_key(cls):
        return '%s.%s' % (DynamicAction.__module__, DynamicAction.__name__)

    def run(self, context):
        return self.action.run(context)

    def is_sync(self):
        return self.action.is_sync()


class DynamicActionDescriptor(ml_actions.PythonActionDescriptor):
    def __init__(self, name, cls_name, action_cls, code_source_id, version,
                 action_cls_attrs=None, namespace='', project_id=None,
                 scope=None):
        super(DynamicActionDescriptor, self).__init__(
            name,
            action_cls,
            action_cls_attrs,
            namespace,
            project_id,
            scope
        )

        self.cls_name = cls_name
        self.code_source_id = code_source_id
        self.version = version

    def __repr__(self):
        return 'Dynamic action [name=%s, cls=%s , code_source_id=%s,' \
               ' version=%s]' % (
                   self.name,
                   self._action_cls,
                   self.code_source_id,
                   self.version
               )

    def instantiate(self, params, wf_ctx):
        if not self._action_cls_attrs:
            # No need to create new dynamic type.
            return DynamicAction(
                self._action_cls(**params),
                self.code_source_id,
                self.namespace
            )

        dynamic_cls = type(
            self._action_cls.__name__,
            (self._action_cls,),
            **self._action_cls_attrs
        )

        return DynamicAction(
            dynamic_cls(**params),
            self.code_source_id,
            self.namespace
        )


class DynamicActionSerializer(serialization.DictBasedSerializer):
    def serialize_to_dict(self, entity):
        cls = type(entity.action)

        return {
            'cls_name': cls.__name__,
            'cls_attrs': inspect_utils.get_public_fields(cls),
            'data': vars(entity.action),
            'code_source_id': entity.code_source_id,
            'namespace': entity.namespace,
        }

    def deserialize_from_dict(self, entity_dict):
        cls_name = entity_dict['cls_name']

        mod = _get_python_module(
            entity_dict['code_source_id'],
            entity_dict['namespace']
        )

        cls = getattr(mod[0], cls_name)

        cls_attrs = entity_dict['cls_attrs']

        if cls_attrs:
            cls = type(cls.__name__, (cls,), cls_attrs)

        action = cls.__new__(cls)

        for k, v in entity_dict['data'].items():
            setattr(action, k, v)

        return DynamicAction(
            action,
            entity_dict['code_source_id'],
            entity_dict['namespace']
        )


def _get_python_module(code_source_id, namespace=''):
    code_source = db_api.get_code_source(
        code_source_id,
        namespace=namespace
    )

    mod = _load_python_module(code_source.name, code_source.content)

    return mod, code_source.version


def _load_python_module(fullname, content):
    mod = types.ModuleType(fullname)

    exec(content, mod.__dict__)

    return mod


serialization.register_serializer(DynamicAction, DynamicActionSerializer())


class DynamicActionProvider(ml_actions.ActionProvider):
    """Provides dynamic actions."""

    def __init__(self, name='dynamic'):
        super().__init__(name)

        # {code_source_id => (python module, version)}
        self._code_sources = dict()

    def ensure_latest_module_version(self, action_def):
        # We need to compare the version of the corresponding module
        # that's already loaded into memory with the version stored in
        # DB and reimport the module if the DB version is higher.

        code_src_id = action_def.code_source_id

        # TODO(rakhmerov): To avoid this DB call we need to store code source
        # versions also in the dynamic action definition model.
        db_ver = db_api.get_code_source(code_src_id, fields=['version'])[0]

        if db_ver > self._code_sources.get(code_src_id, (None, -1))[1]:
            # Reload module.
            code_src = db_api.get_code_source(code_src_id)

            module = _load_python_module(code_src.name, code_src.content)

            self._code_sources[code_src_id] = (module, code_src.version)
        else:
            module = self._code_sources[code_src_id][0]

        return module

    def _get_action_class(self, action_def):
        module = self.ensure_latest_module_version(action_def)

        return getattr(module, action_def.class_name)

    def _build_action_descriptor(self, action_def):
        action_cls = self._get_action_class(action_def)

        return DynamicActionDescriptor(
            name=action_def.name,
            cls_name=action_def.class_name,
            action_cls=action_cls,
            code_source_id=action_def.code_source_id,
            version=1,
            project_id=action_def.project_id,
            scope=action_def.scope
        )

    def find(self, action_name, namespace=None):
        action_def = db_api.load_dynamic_action_definition(
            action_name,
            namespace
        )

        if action_def is None:
            return None

        return self._build_action_descriptor(action_def)

    def find_all(self, namespace='', limit=None, sort_fields=None,
                 sort_dirs=None, filters=None):
        if filters is None:
            filters = dict()

        filters['namespace'] = {'eq': namespace}

        action_defs = db_api.get_dynamic_action_definitions(
            limit=limit,
            sort_keys=sort_fields,
            sort_dirs=sort_dirs,
            **filters
        )

        return [self._build_action_descriptor(a_d) for a_d in action_defs]
