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

import inspect
import json


def get_public_fields(obj):
    """Returns only public fields from object or class."""

    public_attributes = [attr for attr in dir(obj)
                         if not attr.startswith("_")]

    public_fields = {}

    for attribute_str in public_attributes:
        attr = getattr(obj, attribute_str)
        is_field = not (inspect.isbuiltin(attr)
                        or inspect.isfunction(attr)
                        or inspect.ismethod(attr))

        if is_field:
            public_fields[attribute_str] = attr

    return public_fields


def get_docstring(obj):
    return inspect.getdoc(obj)


def get_arg_list(func):
    argspec = inspect.getargspec(func)

    args = argspec.args

    if 'self' in args:
        args.remove('self')

    return args


def get_arg_list_as_str(func):
    args = getattr(func, "__arguments__", None)
    if args:
        return args

    argspec = inspect.getargspec(func)
    defs = list(argspec.defaults or [])

    args = get_arg_list(func)

    diff_args_defs = len(args) - len(defs)
    arg_str_list = []

    for index, default in enumerate(args):
        if index >= diff_args_defs:
            try:
                arg_str_list.append(
                    "%s=%s" % (
                        args[index],
                        json.dumps(defs[index - diff_args_defs])
                    )
                )
            except TypeError:
                pass
        else:
            arg_str_list.append("%s" % args[index])

    if argspec.keywords:
        arg_str_list.append("**%s" % argspec.keywords)

    return ", ".join(arg_str_list)
