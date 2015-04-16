# Copyright 2015 - Mirantis, Inc.
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
import six
import types

import yaql
from yaql import context


def create_yaql_context():
    ctx = yaql.create_context()

    _register_functions(ctx)

    return ctx


def _register_functions(yaql_ctx):
    yaql_ctx.register_function(_string_and_iterable_length, 'len')
    yaql_ctx.register_function(_generator_length, 'len')
    yaql_ctx.register_function(to_str, 'str')


# Additional convenience YAQL functions.


@context.EvalArg('a', arg_type=(six.string_types, collections.Iterable))
def _string_and_iterable_length(a):
    return len(a)


@context.EvalArg('a', arg_type=types.GeneratorType)
def _generator_length(a):
    return sum(1 for i in a)


def to_str(value):
    return str(value())