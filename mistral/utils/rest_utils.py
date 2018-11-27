# Copyright 2014 - Mirantis, Inc.
# Copyright 2016 - Brocade Communications Systems, Inc.
# Copyright 2018 - Nokia, Inc.
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

from oslo_db import exception as db_exc
from oslo_log import log as logging
import pecan
import six
import sqlalchemy as sa
import tenacity
import webob
from wsme import exc as wsme_exc


from mistral import context as auth_ctx
from mistral.db import utils as db_utils
from mistral.db.v2.sqlalchemy import api as db_api
from mistral import exceptions as exc


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
        except (exc.MistralException, exc.MistralError) as e:
            pecan.response.translatable_error = e

            LOG.error('Error during API call: %s', str(e))

            raise wsme_exc.ClientSideError(
                msg=six.text_type(e),
                status_code=e.http_code
            )

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
        except (exc.MistralException, exc.MistralError) as e:
            LOG.error('Error during API call: %s', str(e))

            return webob.Response(
                status=e.http_code,
                content_type='application/json',
                body=json.dumps(dict(faultstring=six.text_type(e))),
                charset='UTF-8'
            )

    return wrapped


def validate_query_params(limit, sort_keys, sort_dirs):
    if limit is not None and limit <= 0:
        raise wsme_exc.ClientSideError("Limit must be positive.")

    if len(sort_keys) < len(sort_dirs):
        raise wsme_exc.ClientSideError(
            "Length of sort_keys must be equal or greater than sort_dirs."
        )

    if len(sort_keys) > len(sort_dirs):
        sort_dirs.extend(['asc'] * (len(sort_keys) - len(sort_dirs)))

    for sort_dir in sort_dirs:
        if sort_dir not in ['asc', 'desc']:
            raise wsme_exc.ClientSideError(
                "Unknown sort direction, must be 'desc' or 'asc'."
            )


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
        raise wsme_exc.ClientSideError(
            'Some fields do not exist  [%s], please choose from [%s]' %
            (', '.join(invalid_fields), ', '.join(object_fields))
        )


def filters_to_dict(**kwargs):
    """Return only non-null values

    :param kwargs: All possible filters
    :type kwargs: dict
    :return: Actual filters
    :rtype: dict
    """
    return {k: v for k, v in kwargs.items() if v is not None}


def get_all(list_cls, cls, get_all_function, get_function,
            resource_function=None, marker=None, limit=None,
            sort_keys=None, sort_dirs=None, fields=None,
            all_projects=False, **filters):
    """Return a list of cls.

    :param list_cls: REST Resource collection class (e.g.: Actions,
        Workflows, ...)
    :param cls: REST Resource class (e.g.: Action, Workflow, ...)
    :param get_all_function: Request function to get all elements with
                             filtering (limit, marker, sort_keys, sort_dirs,
                             fields)
    :param get_function: Function used to fetch the marker
    :param resource_function: Optional, function used to fetch additional data
    :param marker: Optional. Pagination marker for large data sets.
    :param limit: Optional. Maximum number of resources to return in a
                  single result. Default value is None for backward
                  compatibility.
    :param sort_keys: Optional. List of columns to sort results by.
                      Default: ['created_at'].
    :param sort_dirs: Optional. List of directions to sort corresponding to
                      sort_keys, "asc" or "desc" can be chosen.
                      Default: ['asc'].
    :param fields: Optional. A specified list of fields of the resource to
                   be returned. 'id' will be included automatically in
                   fields if it's provided, since it will be used when
                   constructing 'next' link.
    :param filters: Optional. A specified dictionary of filters to match.
    :param all_projects: Optional. Get resources of all projects.
    """
    sort_keys = ['created_at'] if sort_keys is None else sort_keys
    sort_dirs = ['asc'] if sort_dirs is None else sort_dirs
    fields = [] if fields is None else fields

    if fields and 'id' not in fields:
        fields.insert(0, 'id')

    validate_query_params(limit, sort_keys, sort_dirs)
    validate_fields(fields, cls.get_fields())

    # Admin user can get all tenants resources, no matter they are private or
    # public.
    insecure = False

    if (all_projects or
            (auth_ctx.ctx().is_admin and filters.get('project_id', ''))):
        insecure = True

    marker_obj = None

    if marker:
        marker_obj = get_function(marker)

    def _get_all_function():
        with db_api.transaction():
            db_models = get_all_function(
                limit=limit,
                marker=marker_obj,
                sort_keys=sort_keys,
                sort_dirs=sort_dirs,
                insecure=insecure,
                **filters
            )

            for db_model in db_models:
                if resource_function:
                    rest_resource = resource_function(db_model)
                else:
                    rest_resource = cls.from_db_model(db_model)

                rest_resources.append(rest_resource)

    rest_resources = []

    r = create_db_retry_object()

    # If only certain fields are requested then we ignore "resource_function"
    # parameter because it doesn't make sense anymore.
    if fields:
        # Use retries to prevent possible failures.
        db_list = r.call(
            get_all_function,
            limit=limit,
            marker=marker_obj,
            sort_keys=sort_keys,
            sort_dirs=sort_dirs,
            fields=fields,
            insecure=insecure,
            **filters
        )

        for obj_values in db_list:
            # Note: in case if only certain fields have been requested
            # "db_list" contains tuples with values of db objects.
            rest_resources.append(
                cls.from_tuples(zip(fields, obj_values))
            )
    else:
        r.call(_get_all_function)

    return list_cls.convert_with_links(
        rest_resources,
        limit,
        pecan.request.host_url,
        sort_keys=','.join(sort_keys),
        sort_dirs=','.join(sort_dirs),
        fields=','.join(fields) if fields else '',
        **filters
    )


class MistralRetrying(tenacity.Retrying):
    def call(self, fn, *args, **kwargs):
        try:
            return super(MistralRetrying, self).call(fn, *args, **kwargs)
        except tenacity.RetryError:
            raise exc.MistralError("The service is temporarily unavailable")


def create_db_retry_object():
    return MistralRetrying(
        retry=tenacity.retry_if_exception_type(
            (
                sa.exc.OperationalError,
                db_exc.DBDeadlock,
                db_exc.DBConnectionError
            )
        ),
        stop=tenacity.stop_after_attempt(10),
        wait=tenacity.wait_incrementing(increment=0.5)  # 0.5 seconds
    )


def rest_retry_on_db_error(func):
    return db_utils.retry_on_db_error(func, create_db_retry_object())
