# Copyright 2015 OpenStack Foundation.
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

"""Kilo release

Revision ID: 001
Revises: None
Create Date: 2015-03-31 12:02:51.935368

"""

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None

from alembic import op
import sqlalchemy as sa

from mistral.db.sqlalchemy import types as st


def upgrade():
    op.create_table(
        'workbooks_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=True),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('spec', st.JsonEncoded(), nullable=True),
        sa.Column('tags', st.JsonEncoded(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'project_id')
    )
    op.create_table(
        'tasks',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=True),
        sa.Column('requires', st.JsonEncoded(), nullable=True),
        sa.Column('workbook_name', sa.String(length=80), nullable=True),
        sa.Column('execution_id', sa.String(length=36), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('task_spec', st.JsonEncoded(), nullable=True),
        sa.Column('action_spec', st.JsonEncoded(), nullable=True),
        sa.Column('state', sa.String(length=20), nullable=True),
        sa.Column('tags', st.JsonEncoded(), nullable=True),
        sa.Column('in_context', st.JsonEncoded(), nullable=True),
        sa.Column('parameters', st.JsonEncoded(), nullable=True),
        sa.Column('output', st.JsonEncoded(), nullable=True),
        sa.Column('task_runtime_context', st.JsonEncoded(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'action_definitions_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=True),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('spec', st.JsonEncoded(), nullable=True),
        sa.Column('tags', st.JsonEncoded(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('input', sa.Text(), nullable=True),
        sa.Column('action_class', sa.String(length=200), nullable=True),
        sa.Column('attributes', st.JsonEncoded(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'project_id')
    )
    op.create_table(
        'workflow_definitions_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=True),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('spec', st.JsonEncoded(), nullable=True),
        sa.Column('tags', st.JsonEncoded(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'project_id')
    )
    op.create_table(
        'executions_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=True),
        sa.Column('workflow_name', sa.String(length=80), nullable=True),
        sa.Column('spec', st.JsonEncoded(), nullable=True),
        sa.Column('state', sa.String(length=20), nullable=True),
        sa.Column('state_info', sa.String(length=1024), nullable=True),
        sa.Column('tags', st.JsonEncoded(), nullable=True),
        sa.Column('accepted', sa.Boolean(), nullable=True),
        sa.Column('input', st.JsonEncoded(), nullable=True),
        sa.Column('output', st.JsonLongDictType(), nullable=True),
        sa.Column('params', st.JsonEncoded(), nullable=True),
        sa.Column('context', st.JsonEncoded(), nullable=True),
        sa.Column('action_spec', st.JsonEncoded(), nullable=True),
        sa.Column('processed', sa.BOOLEAN(), nullable=True),
        sa.Column('in_context', st.JsonLongDictType(), nullable=True),
        sa.Column('published', st.JsonEncoded(), nullable=True),
        sa.Column('runtime_context', st.JsonEncoded(), nullable=True),
        sa.Column('task_execution_id', sa.String(length=36), nullable=True),
        sa.Column(
            'workflow_execution_id', sa.String(length=36), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ['task_execution_id'], [u'executions_v2.id'],
        ),
        sa.ForeignKeyConstraint(
            ['workflow_execution_id'], [u'executions_v2.id'],
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'workbooks',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('tags', st.JsonEncoded(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('trust_id', sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint('id', 'name'),
        sa.UniqueConstraint('name')
    )
    op.create_table(
        'environments_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('variables', st.JsonEncoded(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'project_id')
    )
    op.create_table(
        'triggers',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('pattern', sa.String(length=20), nullable=False),
        sa.Column('next_execution_time', sa.DateTime(), nullable=False),
        sa.Column('workbook_name', sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_table(
        'delayed_calls_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column(
            'factory_method_path', sa.String(length=200), nullable=True
        ),
        sa.Column('target_method_name', sa.String(length=80), nullable=False),
        sa.Column('method_arguments', st.JsonEncoded(), nullable=True),
        sa.Column('serializers', st.JsonEncoded(), nullable=True),
        sa.Column('auth_context', st.JsonEncoded(), nullable=True),
        sa.Column('execution_time', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'workflow_executions',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workbook_name', sa.String(length=80), nullable=True),
        sa.Column('task', sa.String(length=80), nullable=True),
        sa.Column('state', sa.String(length=20), nullable=True),
        sa.Column('context', st.JsonEncoded(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'cron_triggers_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('pattern', sa.String(length=100), nullable=True),
        sa.Column('next_execution_time', sa.DateTime(), nullable=False),
        sa.Column('workflow_name', sa.String(length=80), nullable=True),
        sa.Column('remaining_executions', sa.Integer(), nullable=True),
        sa.Column('workflow_id', sa.String(length=36), nullable=True),
        sa.Column('workflow_input', st.JsonEncoded(), nullable=True),
        sa.Column('workflow_input_hash', sa.CHAR(length=64), nullable=True),
        sa.Column('trust_id', sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ['workflow_id'], [u'workflow_definitions_v2.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'project_id'),
        sa.UniqueConstraint(
            'workflow_input_hash', 'workflow_name', 'pattern', 'project_id'
        )
    )
