# Copyright 2023 - NetCracker Technology Corp.
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

import copy
import hashlib

from oslo_config import cfg


VERSIONS_KEY = "__versions"


def clear_versions(ctx):
    if VERSIONS_KEY in ctx:
        del ctx[VERSIONS_KEY]


def get_in_context_with_versions(task_ex):
    in_context = task_ex.in_context if task_ex.in_context else {}

    if not cfg.CONF.context_versioning.enabled:
        return in_context

    in_context = (copy.deepcopy(dict(in_context)))

    task_published = task_ex.published or []

    in_context.setdefault(VERSIONS_KEY, {})

    updated_keys = _get_updated_keys(task_published)

    for updated in updated_keys:
        in_context[VERSIONS_KEY].setdefault(updated, 0)
        in_context[VERSIONS_KEY][updated] += 1

    return in_context


def _get_updated_keys(published):
    updated_keys = []
    _get_published_keys_recursively(updated_keys, published)
    return updated_keys


def _get_published_keys_recursively(updated_keys, published, prefix=None):
    for key in published:
        new_prefix = key if not prefix else prefix + "." + key

        if not isinstance(published[key], dict):
            if cfg.CONF.context_versioning.hash_version_keys:
                new_prefix = hashlib.md5(
                    new_prefix.encode("utf-8")
                ).hexdigest()

            updated_keys.append(new_prefix)
        else:
            _get_published_keys_recursively(
                updated_keys,
                published[key],
                new_prefix
            )


def merge_context_by_version(ctx_left, ctx_right):
    versions_left = copy.copy(ctx_left[VERSIONS_KEY])
    versions_right = copy.copy(ctx_right[VERSIONS_KEY])

    _remove_internal_data_from_context(ctx_left)
    _remove_internal_data_from_context(ctx_right)

    result = _merge_ctx(ctx_left, versions_left, ctx_right, versions_right)

    result[VERSIONS_KEY] = _merge_versions(versions_left, versions_right)

    return result


def _get_version(key, versions):
    if key not in versions:
        return 0

    return versions[key]


def _merge_ctx(ctx_left, ver_left, ctx_right, ver_right, prefix=None):
    if ctx_left is None:
        return ctx_right

    if ctx_right is None:
        return ctx_left

    for k, v in ctx_right.items():
        if k not in ctx_left:
            ctx_left[k] = v
        else:
            left_v = ctx_left[k]

            new_prefix = k if not prefix else prefix + "." + k

            if isinstance(left_v, dict) and isinstance(v, dict):
                _merge_ctx(left_v, ver_left, v, ver_right, new_prefix)
            else:
                if cfg.CONF.context_versioning.hash_version_keys:
                    new_prefix = hashlib.md5(
                        new_prefix.encode("utf-8")
                    ).hexdigest()
                l_ver = _get_version(new_prefix, ver_left)
                r_ver = _get_version(new_prefix, ver_right)
                if r_ver > l_ver:
                    ctx_left[k] = v

    return ctx_left


def _merge_versions(ver_left, ver_right):
    for key in ver_right:
        if key not in ver_left:
            ver_left[key] = ver_right[key]
        ver_left[key] = max(ver_left[key], ver_right[key])

    return ver_left


def _remove_internal_data_from_context(ctx):
    if '__task_execution' in ctx:
        del ctx['__task_execution']
    del ctx[VERSIONS_KEY]
