# Copyright 2026 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Backfill empty namespace on action_definitions_v2.

Revision ID: 046
Revises: 045
Create Date: 2026-11-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import column
from sqlalchemy.sql import table

# revision identifiers, used by Alembic.
revision = '046'
down_revision = '045'


def upgrade():
    action_def = table(
        'action_definitions_v2',
        column('id'),
        column('name'),
        column('namespace'),
        column('project_id'),
    )
    other = action_def.alias()

    # Rows already shadowed by a '' twin would violate the unique key.
    shadowed = sa.exists().where(
        other.c.name == action_def.c.name,
        other.c.project_id == action_def.c.project_id,
        other.c.namespace == '',
    )

    bind = op.get_bind()

    # MySQL cannot UPDATE a table referenced in its own subquery.
    # NULL twins don't collide under the unique key: backfill one of them.
    ids = [
        row.id
        for row in bind.execute(
            sa.select(sa.func.min(action_def.c.id).label('id'))
            .where(action_def.c.namespace.is_(None), ~shadowed)
            .group_by(action_def.c.name, action_def.c.project_id)
        )
    ]

    if ids:
        bind.execute(
            action_def.update()
            .values(namespace='')
            .where(action_def.c.id.in_(ids))
        )
