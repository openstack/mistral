# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
# Copyright 2016 - Brocade Communications Systems, Inc.
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

from mistral_lib.utils import inspect_utils

from mistral import expressions as expr


def evaluate_object_fields(obj, ctx):
    """Evaluates all expressions recursively contained in the object fields.

    Some of the given object fields may be strings or data structures that
    contain YAQL/Jinja expressions. The method evaluates them and updates
    the corresponding object fields with the evaluated values.

    :param obj: The object to inspect.
    :param ctx: Expression context.
    """
    fields = inspect_utils.get_public_fields(obj)

    evaluated_fields = expr.evaluate_recursively(fields, ctx)

    for k, v in evaluated_fields.items():
        setattr(obj, k, v)
