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

import pecan
import six
from wsme import exc

from mistral import exceptions as ex


def wrap_wsme_controller_exception(func):
    """This decorator wraps controllers method to manage wsme exceptions:
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
    """This decorator wraps controllers method to manage pecan exceptions:
    In case of expected error it aborts the request with specific status code.
    """
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ex.MistralException as excp:
            pecan.response.translatable_error = excp
            pecan.abort(excp.http_code, six.text_type(excp))
    return wrapped
