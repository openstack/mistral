# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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

import cachetools
import threading
import yaml
from yaml import error

import six

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.workbook import base
from mistral.workbook.v2 import actions as actions_v2
from mistral.workbook.v2 import tasks as tasks_v2
from mistral.workbook.v2 import workbook as wb_v2
from mistral.workbook.v2 import workflows as wf_v2

V2_0 = '2.0'

ALL_VERSIONS = [V2_0]


_WF_EX_CACHE = cachetools.LRUCache(maxsize=100)
_WF_EX_CACHE_LOCK = threading.RLock()

_WF_DEF_CACHE = cachetools.LRUCache(maxsize=100)
_WF_DEF_CACHE_LOCK = threading.RLock()


def parse_yaml(text):
    """Loads a text in YAML format as dictionary object.

    :param text: YAML text.
    :return: Parsed YAML document as dictionary.
    """

    try:
        return yaml.safe_load(text) or {}
    except error.YAMLError as e:
        raise exc.DSLParsingException(
            "Definition could not be parsed: %s\n" % e
        )


def _get_spec_version(spec_dict):
    # If version is not specified it will '2.0' by default.
    ver = V2_0

    if 'version' in spec_dict:
        ver = spec_dict['version']

    if not ver or str(float(ver)) not in ALL_VERSIONS:
        raise exc.DSLParsingException('Unsupported DSL version: %s' % ver)

    return ver


# Factory methods to get specifications either from raw YAML formatted text or
# from dictionaries parsed from YAML formatted text.

def get_workbook_spec(spec_dict):
    if _get_spec_version(spec_dict) == V2_0:
        return base.instantiate_spec(wb_v2.WorkbookSpec, spec_dict)

    return None


def get_workbook_spec_from_yaml(text):
    return get_workbook_spec(parse_yaml(text))


def get_action_spec(spec_dict):
    if _get_spec_version(spec_dict) == V2_0:
        return base.instantiate_spec(actions_v2.ActionSpec, spec_dict)

    return None


def get_action_spec_from_yaml(text, action_name):
    spec_dict = parse_yaml(text)

    spec_dict['name'] = action_name

    return get_action_spec(spec_dict)


def get_action_list_spec(spec_dict):
    return base.instantiate_spec(actions_v2.ActionListSpec, spec_dict)


def get_action_list_spec_from_yaml(text):
    return get_action_list_spec(parse_yaml(text))


def get_workflow_spec(spec_dict):
    """Get workflow specification object from dictionary.

    NOTE: For large workflows this method can work very long (seconds).
    For this reason, method 'get_workflow_spec_by_definition_id' or
    'get_workflow_spec_by_execution_id' should be used whenever possible
    because they cache specification objects.

    :param spec_dict: Raw specification dictionary.
    """
    if _get_spec_version(spec_dict) == V2_0:
        return base.instantiate_spec(wf_v2.WorkflowSpec, spec_dict)

    return None


def get_workflow_list_spec(spec_dict):
    return base.instantiate_spec(wf_v2.WorkflowListSpec, spec_dict)


def get_workflow_spec_from_yaml(text):
    return get_workflow_spec(parse_yaml(text))


def get_workflow_list_spec_from_yaml(text):
    return get_workflow_list_spec(parse_yaml(text))


def get_task_spec(spec_dict):
    if _get_spec_version(spec_dict) == V2_0:
        return base.instantiate_spec(tasks_v2.TaskSpec, spec_dict)

    return None


def get_workflow_definition(wb_def, wf_name):
    wf_name = wf_name + ":"

    return _parse_def_from_wb(wb_def, "workflows:", wf_name)


def get_action_definition(wb_def, action_name):
    action_name += ":"

    return _parse_def_from_wb(wb_def, "actions:", action_name)


def _parse_def_from_wb(wb_def, section_name, item_name):
    io = six.StringIO(wb_def[wb_def.index(section_name):])
    io.readline()
    definition = []
    ident = 0
    # Get the indentation of the action/workflow name tag.
    for line in io:
        if item_name == line.strip():
            ident = line.index(item_name)
            definition.append(line.lstrip())
            break

    # Add strings to list unless same/less indentation is found.
    for line in io:
        new_line = line.strip()

        if not new_line:
            definition.append(line)
        elif new_line.startswith("#"):
            new_line = line if ident > line.index("#") else line[ident:]
            definition.append(new_line)
        else:
            temp = line.index(line.lstrip())
            if ident < temp:
                definition.append(line[ident:])
            else:
                break

    io.close()
    definition = ''.join(definition).rstrip() + '\n'

    return definition


# Methods for obtaining specifications in a more efficient way using
# caching techniques.

@cachetools.cached(_WF_EX_CACHE, lock=_WF_EX_CACHE_LOCK)
def get_workflow_spec_by_execution_id(wf_ex_id):
    """Gets workflow specification by workflow execution id.

    The idea is that when a workflow execution is running we
    must be getting the same workflow specification even if

    :param wf_ex_id: Workflow execution id.
    :return:  Workflow specification.
    """
    if not wf_ex_id:
        return None

    wf_ex = db_api.get_workflow_execution(wf_ex_id)

    return get_workflow_spec(wf_ex.spec)


@cachetools.cached(_WF_DEF_CACHE, lock=_WF_DEF_CACHE_LOCK)
def get_workflow_spec_by_definition_id(wf_def_id, wf_def_updated_at):
    """Gets specification by workflow definition id and its 'updated_at'.

    The idea of this method is to return a cached specification for the
    given workflow id and workflow definition 'updated_at'. As long as the
    given workflow definition remains the same in DB users of this method
    will be getting a cached value. Once the workflow definition has
    changed clients will be providing a different 'updated_at' value and
    hence this method will be called and spec is updated for this combination
    of parameters. Old cached values will be kicked out by LRU algorithm
    if the cache runs out of space.

    :param wf_def_id: Workflow definition id.
    :param wf_def_updated_at: Workflow definition 'updated_at' value. It
     serves only as part of cache key and is not explicitly used in the
     method.
    :return: Workflow specification.
    """
    if not wf_def_id:
        return None

    wf_def = db_api.get_workflow_definition(wf_def_id)

    return get_workflow_spec(wf_def.spec)


def cache_workflow_spec_by_execution_id(wf_ex_id, wf_spec):
    with _WF_EX_CACHE_LOCK:
        _WF_EX_CACHE[cachetools.hashkey(wf_ex_id)] = wf_spec


def get_wf_execution_spec_cache_size():
    return len(_WF_EX_CACHE)


def get_wf_definition_spec_cache_size():
    return len(_WF_DEF_CACHE)


def clear_caches():
    """Clears all specification caches."""
    with _WF_EX_CACHE_LOCK:
        _WF_EX_CACHE.clear()

    with _WF_DEF_CACHE_LOCK:
        _WF_DEF_CACHE.clear()
