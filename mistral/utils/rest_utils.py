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

import functools
import json

import pecan
import six
from webob import Response
from wsme import exc

from mistral import exceptions as ex


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
