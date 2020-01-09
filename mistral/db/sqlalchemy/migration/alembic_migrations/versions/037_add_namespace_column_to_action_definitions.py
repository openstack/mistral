# Copyright 2020 Nokia Software.
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

"""add namespace column to action definitions

Revision ID: 037
Revises: 036
Create Date: 2020-1-6 10:22:20

"""

# revision identifiers, used by Alembic.

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection
from sqlalchemy.sql import table, column

revision = '037'
down_revision = '036'


def upgrade():
    op.add_column(
        'action_definitions_v2',
        sa.Column('namespace', sa.String(length=255), nullable=True)
    )

    inspect = reflection.Inspector.from_engine(op.get_bind())

    unique_constraints = [
        unique_constraint['name'] for unique_constraint in
        inspect.get_unique_constraints('action_definitions_v2')
    ]
    if 'name' in unique_constraints:
        op.drop_index('name', table_name='action_definitions_v2')

    if 'action_definitions_v2_name_project_id_key' in unique_constraints:
        op.drop_constraint('action_definitions_v2_name_project_id_key',
                           table_name='action_definitions_v2')

    op.create_unique_constraint(
        None,
        'action_definitions_v2',
        ['name', 'namespace', 'project_id']
    )

    action_def = table('action_definitions_v2', column('namespace'))
    session = sa.orm.Session(bind=op.get_bind())
    with session.begin(subtransactions=True):
        session.execute(
            action_def.update().values(namespace='').where(
                action_def.c.namespace is None))  # noqa

    session.commit()
