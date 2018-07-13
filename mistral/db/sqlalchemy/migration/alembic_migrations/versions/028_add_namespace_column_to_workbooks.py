# Copyright 2018 OpenStack Foundation.
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

"""add namespace column to workbooks

Revision ID: 028
Revises: 027
Create Date: 2018-07-17 15:39:25.031935

"""

# revision identifiers, used by Alembic.
revision = '028'
down_revision = '027'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


def upgrade():

    op.add_column(
        'workbooks_v2',
        sa.Column('namespace', sa.String(length=255), nullable=True)
    )

    inspect = reflection.Inspector.from_engine(op.get_bind())

    unique_constraints = [
        unique_constraint['name'] for unique_constraint in
        inspect.get_unique_constraints('workbooks_v2')
    ]

    if 'name' in unique_constraints:
        op.drop_index('name', table_name='workbooks_v2')

    op.create_unique_constraint(
        None,
        'workbooks_v2',
        ['name', 'namespace', 'project_id']
    )
