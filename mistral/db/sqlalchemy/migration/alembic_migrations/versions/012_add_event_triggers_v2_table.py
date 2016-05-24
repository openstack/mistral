# Copyright 2016 OpenStack Foundation.
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

"""add event triggers table

Revision ID: 012
Revises: 011
Create Date: 2016-03-04 09:49:52.481791

"""

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'

from alembic import op
import sqlalchemy as sa

from mistral.db.sqlalchemy import types as st


def upgrade():
    op.create_table(
        'event_triggers_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('workflow_id', sa.String(length=36), nullable=False),
        sa.Column('exchange', sa.String(length=80), nullable=False),
        sa.Column('topic', sa.String(length=80), nullable=False),
        sa.Column('event', sa.String(length=80), nullable=False),
        sa.Column('workflow_params', st.JsonEncoded(), nullable=True),
        sa.Column('workflow_input', st.JsonEncoded(), nullable=True),
        sa.Column('trust_id', sa.String(length=80), nullable=True),

        sa.ForeignKeyConstraint(
            ['workflow_id'],
            [u'workflow_definitions_v2.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'exchange',
            'topic',
            'event',
            'workflow_id',
            'project_id'
        ),
        sa.Index(
            'event_triggers_v2_project_id_workflow_id',
            'project_id', 'workflow_id'
        )
    )
