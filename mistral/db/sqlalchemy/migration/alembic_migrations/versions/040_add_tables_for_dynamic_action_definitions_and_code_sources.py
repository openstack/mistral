# Copyright 2020 Nokia Software.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""create new tables for the dynamic actions and code sources

Revision ID: 001
Revises: None
Create Date: 2020-09-30 12:02:51.935368

"""

# revision identifiers, used by Alembic.
revision = '040'
down_revision = '039'

from alembic import op
from mistral.db.sqlalchemy import types as st
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'code_sources',

        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('namespace', sa.String(length=255), nullable=True),
        sa.Column('content', sa.TEXT, nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('tags', st.JsonEncoded(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'namespace', 'project_id'),

        sa.Index('code_sources_project_id', 'project_id'),
        sa.Index('code_sources_scope', 'scope')
    )

    op.create_table(
        'dynamic_action_definitions',

        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('class_name', sa.String(length=255), nullable=False),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('code_source_id', sa.String(length=36), nullable=False),
        sa.Column('code_source_name', sa.String(length=255), nullable=False),
        sa.Column('namespace', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['code_source_id'],
            ['code_sources.id'],
            ondelete='CASCADE'
        ),

        sa.UniqueConstraint('name', 'namespace', 'project_id'),

        sa.Index('dynamic_action_definitions_project_id', 'project_id'),
        sa.Index('dynamic_action_definitions_scope', 'scope'),

    )
