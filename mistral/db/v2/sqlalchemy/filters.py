#    Copyright 2016 NEC Corporation.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_serialization import jsonutils
import sqlalchemy as sa
from sqlalchemy.ext import compiler
from sqlalchemy.sql import expression

from mistral.db.sqlalchemy import types as st


class JsonKeyEquals(expression.ColumnElement):
    inherit_cache = False
    type = sa.Boolean()

    def __init__(self, column, key, value):
        self.column = column
        self.path = '$.' + jsonutils.dumps(key)
        self.value = jsonutils.dumps(value)
        self.wrapped = jsonutils.dumps({'v': value})


@compiler.compiles(JsonKeyEquals)
def _compile_json_key_equals(element, compiler, **kw):
    raise NotImplementedError(
        'JSON filters are not supported on %s' % compiler.dialect.name
    )


@compiler.compiles(JsonKeyEquals, 'mysql')
@compiler.compiles(JsonKeyEquals, 'mariadb')
def _compile_json_key_equals_mysql(element, compiler, **kw):
    extracted = sa.func.json_extract(element.column, element.path)
    value = sa.literal(element.value)

    return compiler.process(
        sa.and_(
            sa.func.json_contains(extracted, value),
            sa.func.json_contains(value, extracted)
        ),
        **kw
    )


@compiler.compiles(JsonKeyEquals, 'sqlite')
def _compile_json_key_equals_sqlite(element, compiler, **kw):
    wrapped = sa.literal(element.wrapped)

    return compiler.process(
        sa.and_(
            sa.func.json_valid(element.column),
            sa.func.json_extract(element.column, element.path) ==
            sa.func.json_extract(wrapped, '$.v'),
            sa.func.json_type(element.column, element.path) ==
            sa.func.json_type(wrapped, '$.v')
        ),
        **kw
    )


def _is_json_column(column_attr):
    return isinstance(getattr(column_attr, 'type', None), st.JsonEncoded)


def apply_filters(query, model, **filters):
    filter_dict = {}

    for key, value in filters.items():
        column_attr = getattr(model, key)

        if key == 'tags':
            continue

        if (isinstance(value, dict) and isinstance(value.get('eq'), dict)
                and _is_json_column(column_attr)):
            for k, v in value['eq'].items():
                query = query.filter(JsonKeyEquals(column_attr, k, v))
        elif isinstance(value, dict):
            if 'in' in value:
                query = query.filter(column_attr.in_(value['in']))
            elif 'nin' in value:
                query = query.filter(~column_attr.in_(value['nin']))
            elif 'neq' in value:
                query = query.filter(column_attr != value['neq'])
            elif 'gt' in value:
                query = query.filter(column_attr > value['gt'])
            elif 'gte' in value:
                query = query.filter(column_attr >= value['gte'])
            elif 'lt' in value:
                query = query.filter(column_attr < value['lt'])
            elif 'lte' in value:
                query = query.filter(column_attr <= value['lte'])
            elif 'eq' in value:
                query = query.filter(column_attr == value['eq'])
            elif 'has' in value:
                like_pattern = '%{0}%'.format(value['has'])

                query = query.filter(column_attr.like(like_pattern))
        else:
            filter_dict[key] = value

    # We need to handle tag case seprately. As tag datatype is MutableList.
    # TODO(hparekh): Need to think how can we get rid of this.
    tags = filters.pop('tags', None)

    if isinstance(tags, dict):
        tags = tags.get("eq")

    # To match the tag list, a resource must contain at least all of the
    # tags present in the filter parameter.
    if tags:
        if ',' in tags:
            tags = tags.split(',')

        tag_attr = getattr(model, 'tags')

        if not isinstance(tags, list):
            expr = tag_attr.contains(tags)
        else:
            expr = sa.and_(*[tag_attr.contains(tag) for tag in tags])

        query = query.filter(expr)

    if filter_dict:
        query = query.filter_by(**filter_dict)

    return query
