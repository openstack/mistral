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

"""split_execution_table_increase_names

Revision ID: 013
Revises: 012
Create Date: 2016-08-02 11:03:03.263944

"""

# revision identifiers, used by Alembic.

from mistral.db.sqlalchemy import types as st

from alembic import op
import sqlalchemy as sa

revision = '013'
down_revision = '012'


def upgrade():

    op.create_table(
        'action_executions_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('workflow_name', sa.String(length=255), nullable=True),
        sa.Column('workflow_id', sa.String(length=80), nullable=True),
        sa.Column('spec', st.JsonMediumDictType(), nullable=True),
        sa.Column('state', sa.String(length=20), nullable=True),
        sa.Column('state_info', sa.TEXT(), nullable=True),
        sa.Column('tags', st.JsonListType(), nullable=True),
        sa.Column('runtime_context', st.JsonLongDictType(), nullable=True),
        sa.Column('accepted', sa.Boolean(), nullable=True),
        sa.Column('input', st.JsonLongDictType(), nullable=True),
        sa.Column('output', st.JsonLongDictType(), nullable=True),
        sa.Column('task_execution_id', sa.String(length=36), nullable=True),

        sa.PrimaryKeyConstraint('id'),

        sa.Index(
            'action_executions_v2_project_id',
            'project_id'
        ),
        sa.Index(
            'action_executions_v2_scope',
            'scope'
        ),
        sa.Index(
            'action_executions_v2_state',
            'state'
        ),
        sa.Index(
            'action_executions_v2_updated_at',
            'updated_at'
        ),
    )

    op.create_table(
        'workflow_executions_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('workflow_name', sa.String(length=255), nullable=True),
        sa.Column('workflow_id', sa.String(length=80), nullable=True),
        sa.Column('spec', st.JsonMediumDictType(), nullable=True),
        sa.Column('state', sa.String(length=20), nullable=True),
        sa.Column('state_info', sa.TEXT(), nullable=True),
        sa.Column('tags', st.JsonListType(), nullable=True),
        sa.Column('runtime_context', st.JsonLongDictType(), nullable=True),
        sa.Column('accepted', sa.Boolean(), nullable=True),
        sa.Column('input', st.JsonLongDictType(), nullable=True),
        sa.Column('output', st.JsonLongDictType(), nullable=True),
        sa.Column('params', st.JsonLongDictType(), nullable=True),
        sa.Column('context', st.JsonLongDictType(), nullable=True),
        sa.Column('task_execution_id', sa.String(length=36), nullable=True),

        sa.PrimaryKeyConstraint('id'),

        sa.Index(
            'workflow_executions_v2_project_id',
            'project_id'
        ),
        sa.Index(
            'workflow_executions_v2_scope',
            'scope'
        ),
        sa.Index(
            'workflow_executions_v2_state',
            'state'
        ),
        sa.Index(
            'workflow_executions_v2_updated_at',
            'updated_at'
        ),
    )

    op.create_table(
        'task_executions_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.String(length=80), nullable=True),
        sa.Column('project_id', sa.String(length=80), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('workflow_name', sa.String(length=255), nullable=True),
        sa.Column('workflow_id', sa.String(length=80), nullable=True),
        sa.Column('spec', st.JsonMediumDictType(), nullable=True),
        sa.Column('state', sa.String(length=20), nullable=True),
        sa.Column('state_info', sa.TEXT(), nullable=True),
        sa.Column('tags', st.JsonListType(), nullable=True),
        sa.Column('runtime_context', st.JsonLongDictType(), nullable=True),
        sa.Column('action_spec', st.JsonLongDictType(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=True),
        sa.Column('in_context', st.JsonLongDictType(), nullable=True),
        sa.Column('published', st.JsonLongDictType(), nullable=True),
        sa.Column(
            'workflow_execution_id',
            sa.String(length=36),
            nullable=True
        ),

        sa.PrimaryKeyConstraint('id'),

        sa.Index(
            'task_executions_v2_project_id',
            'project_id'
        ),
        sa.Index(
            'task_executions_v2_scope',
            'scope'
        ),
        sa.Index(
            'task_executions_v2_state',
            'state'
        ),
        sa.Index(
            'task_executions_v2_updated_at',
            'updated_at'
        ),
        sa.Index(
            'task_executions_v2_workflow_execution_id',
            'workflow_execution_id'
        ),
        sa.ForeignKeyConstraint(
            ['workflow_execution_id'],
            [u'workflow_executions_v2.id'],
            ondelete='CASCADE'
        ),
    )

    # 2 foreign keys are added here because all 3 tables are dependent.
    op.create_foreign_key(
        None,
        'action_executions_v2',
        'task_executions_v2',
        ['task_execution_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        None,
        'workflow_executions_v2',
        'task_executions_v2',
        ['task_execution_id'],
        ['id'],
        ondelete='CASCADE'
    )

    op.alter_column(
        'workbooks_v2',
        'name',
        type_=sa.String(length=255)
    )
    op.alter_column(
        'workbooks_v2',
        'definition',
        type_=st.MediumText()
    )
    op.alter_column(
        'workbooks_v2',
        'spec',
        type_=st.JsonMediumDictType()
    )

    op.alter_column(
        'workflow_definitions_v2',
        'name',
        type_=sa.String(length=255)
    )
    op.alter_column(
        'workflow_definitions_v2',
        'definition',
        type_=st.MediumText()
    )
    op.alter_column(
        'workflow_definitions_v2',
        'spec',
        type_=st.JsonMediumDictType()
    )

    op.alter_column(
        'action_definitions_v2',
        'name',
        type_=sa.String(length=255)
    )
    op.alter_column(
        'action_definitions_v2',
        'definition',
        type_=st.MediumText()
    )
    op.alter_column(
        'action_definitions_v2',
        'spec',
        type_=st.JsonMediumDictType()
    )

    op.alter_column(
        'cron_triggers_v2',
        'workflow_name',
        type_=sa.String(length=255)
    )
