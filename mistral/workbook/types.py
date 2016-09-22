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

from mistral import expressions


NONEMPTY_STRING = {
    "type": "string",
    "minLength": 1
}

UNIQUE_STRING_LIST = {
    "type": "array",
    "items": NONEMPTY_STRING,
    "uniqueItems": True,
    "minItems": 1
}

POSITIVE_INTEGER = {
    "type": "integer",
    "minimum": 0
}

POSITIVE_NUMBER = {
    "type": "number",
    "minimum": 0.0
}

EXPRESSION = {
    "oneOf": [{
        "type": "string",
        "pattern": "^%s\\s*$" % expressions.patterns[name]
    } for name in expressions.patterns]
}

EXPRESSION_CONDITION = {
    "type": "object",
    "minProperties": 1,
    "patternProperties": {
        "^\w+$": EXPRESSION
    }
}

ANY = {
    "anyOf": [
        {"type": "array"},
        {"type": "boolean"},
        {"type": "integer"},
        {"type": "number"},
        {"type": "object"},
        {"type": "string"}
    ]
}

ANY_NULLABLE = {
    "anyOf": [
        {"type": "null"},
        {"type": "array"},
        {"type": "boolean"},
        {"type": "integer"},
        {"type": "number"},
        {"type": "object"},
        {"type": "string"}
    ]
}

NONEMPTY_DICT = {
    "type": "object",
    "minProperties": 1,
    "patternProperties": {
        "^\w+$": ANY_NULLABLE
    }
}

ONE_KEY_DICT = {
    "type": "object",
    "minProperties": 1,
    "maxProperties": 1,
    "patternProperties": {
        "^\w+$": ANY_NULLABLE
    }
}

STRING_OR_EXPRESSION_CONDITION = {
    "oneOf": [
        NONEMPTY_STRING,
        EXPRESSION_CONDITION
    ]
}

EXPRESSION_OR_POSITIVE_INTEGER = {
    "oneOf": [
        EXPRESSION,
        POSITIVE_INTEGER
    ]
}

EXPRESSION_OR_BOOLEAN = {
    "oneOf": [
        EXPRESSION,
        {"type": "boolean"}
    ]
}


UNIQUE_STRING_OR_EXPRESSION_CONDITION_LIST = {
    "type": "array",
    "items": STRING_OR_EXPRESSION_CONDITION,
    "uniqueItems": True,
    "minItems": 1
}

VERSION = {
    "anyOf": [
        NONEMPTY_STRING,
        POSITIVE_INTEGER,
        POSITIVE_NUMBER
    ]
}

WORKFLOW_TYPE = {
    "enum": ["reverse", "direct"]
}

STRING_OR_ONE_KEY_DICT = {
    "oneOf": [
        NONEMPTY_STRING,
        ONE_KEY_DICT
    ]
}

UNIQUE_STRING_OR_ONE_KEY_DICT_LIST = {
    "type": "array",
    "items": STRING_OR_ONE_KEY_DICT,
    "uniqueItems": True,
    "minItems": 1
}
