# -*- coding: utf-8 -*-
#
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

from oslo_log import log as logging
import functools
import json

import pecan
import six
from webob import Response
from wsme import exc

from mistral import exceptions as ex

LOG = logging.getLogger(__name__)

def wrap_wsme_controller_exception(func):
    """Decorator for controllers method.

    This decorator wraps controllers method to manage wsme exceptions:
    In case of expected error it aborts the request with specific status code.
    """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ex.MistralException as excp:
            pecan.response.translatable_error = excp
            raise exc.ClientSideError(msg=six.text_type(excp),
                                      status_code=excp.http_code)
    return wrapped


def wrap_pecan_controller_exception(func):
    """Decorator for controllers method.

    This decorator wraps controllers method to manage pecan exceptions:
    In case of expected error it aborts the request with specific status code.
    """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ex.MistralException as excp:
            return Response(
                status=excp.http_code,
                content_type='application/json',
                body=json.dumps(dict(
                    faultstring=six.text_type(excp))))

    return wrapped


def validate_query_params(limit, sort_keys, sort_dirs):
    if limit is not None and limit <= 0:
        raise exc.ClientSideError("Limit must be positive.")

    if len(sort_keys) < len(sort_dirs):
        raise exc.ClientSideError("Length of sort_keys must be equal or "
                                  "greater than sort_dirs.")

    if len(sort_keys) > len(sort_dirs):
        sort_dirs.extend(['asc'] * (len(sort_keys) - len(sort_dirs)))

    for sort_dir in sort_dirs:
        if sort_dir not in ['asc', 'desc']:
            raise exc.ClientSideError("Unknown sort direction, must be 'desc' "
                                      "or 'asc'.")


def validate_fields(fields, object_fields):
    """Check for requested non-existent fields.

    Check if the user requested non-existent fields.

    :param fields: A list of fields requested by the user.
    :param object_fields: A list of fields supported by the object.
    """
    if not fields:
        return

    invalid_fields = set(fields) - set(object_fields)

    if invalid_fields:
        raise exc.ClientSideError(
            'Field(s) %s are invalid.' % ', '.join(invalid_fields)
        )


def get_all(list_cls, cls, get_all_function, get_function, collection_name,
                marker=None, limit=None, sort_keys='created_at', sort_dirs='asc',
                fields=''):

    """Return a list of cls.

    :param list_cls: Class list (ex: Actions, Workflows, ...).
    :param cls: Class (ex: Action, Workflow, ...).
    :param marker: Optional. Pagination marker for large data sets.
    :param limit: Optional. Maximum number of resources to return in a
                  single result. Default value is None for backward
                  compatibility.
    :param sort_keys: Optional. Columns to sort results by.
                      Default: created_at.
    :param sort_dirs: Optional. Directions to sort corresponding to
                      sort_keys, "asc" or "desc" can be choosed.
                      Default: asc.
    :param fields: Optional. A specified list of fields of the resource to
                   be returned. 'id' will be included automatically in
                   fields if it's provided, since it will be used when
                   constructing 'next' link.

    """

    LOG.info("Fetch %s. marker=%s, limit=%s, sort_keys=%s, "
         "sort_dirs=%s, fields=%s", collection_name, marker, limit, sort_keys,
         sort_dirs, fields)

    if fields and 'id' not in fields:
        fields.insert(0, 'id')

    validate_query_params(limit, sort_keys, sort_dirs)
    validate_fields(fields, cls.get_fields())

    marker_obj = None

    if marker:
        marker_obj = get_function(marker)

    db_list = get_all_function(
        limit=limit,
        marker=marker_obj,
        sort_keys=sort_keys,
        sort_dirs=sort_dirs,
        fields=fields
    )

    list_to_return = []

    for data in db_list:
        dict_data = (dict(zip(fields, data)) if fields else
                                 data.to_dict())
        list_to_return.append(cls.from_dict(dict_data))

    return list_cls.convert_with_links(
        list_to_return,
        limit,
        pecan.request.host_url,
        sort_keys=','.join(sort_keys),
        sort_dirs=','.join(sort_dirs),
        fields=','.join(fields) if fields else ''
    )