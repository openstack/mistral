# Copyright 2015 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""add_resource_members_v2_table

Revision ID: 010
Revises: 009
Create Date: 2015-11-15 08:39:58.772417

"""

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'resource_members_v2',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=False),
        sa.Column('member_id', sa.String(length=80), nullable=False),
        sa.Column('resource_id', sa.String(length=80), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'resource_id',
            'resource_type',
            'member_id'
        )
    )
