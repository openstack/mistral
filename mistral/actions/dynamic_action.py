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
import types

from mistral import exceptions as exc
from mistral_lib import actions as ml_actions
from mistral_lib import serialization
from mistral_lib.utils import inspect_utils

from mistral.db.v2 import api as db_api
from mistral.services import code_sources as code_sources_service

CONF = cfg.CONF


class DynamicAction(ml_actions.Action):

    def __init__(self, action, code_source_id, namespace=''):
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
    def __init__(self, name, cls_name, action_cls, version, code_source_id,
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
        self.version = version
        self.code_source_id = code_source_id

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
                self.namespace)

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

        mod = _get_module(
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


def _get_module(code_source_id, namespace=''):
    code_source = code_sources_service.get_code_source(
        code_source_id,
        namespace
    )

    mod = _load_module(code_source.name, code_source.src)

    return mod, code_source.version


def _load_module(fullname, content):
    mod = types.ModuleType(fullname)

    exec(content, mod.__dict__)

    return mod


serialization.register_serializer(DynamicAction, DynamicActionSerializer())


class DynamicActionProvider(ml_actions.ActionProvider):
    """Provides dynamic actions."""

    def __init__(self, name='dynamic'):
        super().__init__(name)

        self._action_descs = collections.OrderedDict()
        self._code_sources = collections.OrderedDict()

    def _get_code_source_version(self, code_src_id, namespace=''):
        code_src = code_sources_service.get_code_source(
            code_src_id,
            namespace,
            fields=['version']
        )

        return code_src[0]

    def _load_code_source(self, id):
        mod_pair = _get_module(id)
        self._code_sources[id] = mod_pair

        return mod_pair

    def _get_code_source(self, id):
        mod_pair = self._code_sources.get(id)
        code_src_db_version = self._get_code_source_version(id)

        if not mod_pair or mod_pair[1] != code_src_db_version:
            mod_pair = self._load_code_source(id)

        return mod_pair

    def _get_action_from_db(self, name, namespace, fields=()):
        action = None

        try:
            action = db_api.get_dynamic_action(
                identifier=name,
                namespace=namespace,
                fields=fields
            )
        except exc.DBEntityNotFoundError:
            pass

        return action

    def _action_exists_in_db(self, name, namespace):
        action = self._get_action_from_db(
            name,
            namespace,
            fields=['name']
        )

        return action is not None

    def _reload_action(self, action_desc, mod_pair):
        action_desc._action_cls = getattr(
            mod_pair[0],
            action_desc.cls_name
        )

        action_desc.version = mod_pair[1]

    def _load_new_action(self, action_name, namespace, action_def):
        # only query the db if action_def was None
        action_def = action_def or self._get_action_from_db(
            action_name,
            namespace=namespace
        )

        if not action_def:
            return

        mod_pair = self._get_code_source(action_def.code_source_id)

        cls = getattr(mod_pair[0], action_def.class_name)

        action_desc = DynamicActionDescriptor(
            name=action_def.name,
            action_cls=cls,
            cls_name=action_def.class_name,
            version=1,
            code_source_id=action_def.code_source_id
        )

        self._action_descs[(action_name, namespace)] = action_desc

        return action_desc

    def _load_existing_action(self, action_desc, action_name, namespace):
        if not self._action_exists_in_db(action_name, namespace=namespace):
            # deleting action from cache
            del self._action_descs[(action_name, namespace)]

            return

        mod_pair = self._get_code_source(action_desc.code_source_id)

        if action_desc.version != mod_pair[1]:
            self._reload_action(action_desc, mod_pair)

        return action_desc

    def _load_action(self, action_name, namespace=None, action_def=None):
        action_desc = self._action_descs.get((action_name, namespace))

        if action_desc:
            action_desc = self._load_existing_action(
                action_desc,
                action_name,
                namespace
            )
        else:
            action_desc = self._load_new_action(
                action_name,
                namespace,
                action_def
            )

        return action_desc

    def find(self, action_name, namespace=None):

        return self._load_action(action_name, namespace)

    def _clean_deleted_actions_from_cache(self):
        to_delete = [
            key for key in self._action_descs.keys()
            if not self._action_exists_in_db(*key)
        ]

        for key in to_delete:
            del self._action_descs[key]

    def find_all(self, namespace='', limit=None, sort_fields=None,
                 sort_dirs=None, **filters):
        filters = {
            'namespace': {'eq': namespace}
        }
        self._clean_deleted_actions_from_cache()

        actions = db_api.get_dynamic_actions(
            limit=limit,
            sort_keys=sort_fields,
            sort_dirs=sort_dirs,
            **filters
        )

        for action in actions:
            self._load_action(
                action.name,
                namespace=namespace,
                action_def=action
            )

        return dict(filter(
            lambda elem: elem[0][1] == namespace,
            self._action_descs.items())
        )
