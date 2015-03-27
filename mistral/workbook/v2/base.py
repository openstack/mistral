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

from mistral.workbook import base
from mistral.workbook import types


class BaseSpec(base.BaseSpec):
    _version = "2.0"

    _meta_schema = {
        "type": "object",
        "properties": {
            "name": types.NONEMPTY_STRING,
            "version": types.VERSION,
            "description": types.NONEMPTY_STRING,
            "tags": types.UNIQUE_STRING_LIST
        },
        "required": ["name", "version"]
    }


class BaseSpecList(base.BaseSpecList):
    _version = "2.0"


class BaseListSpec(base.BaseListSpec):
    _version = "2.0"
