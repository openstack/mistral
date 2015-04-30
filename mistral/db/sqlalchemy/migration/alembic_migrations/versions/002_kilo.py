# Copyright 2015 OpenStack Foundation.
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

"""Kilo

Revision ID: 002
Revises: 001
Create Date: 2015-04-30 16:15:34.737030

"""

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'

from alembic import op
import sqlalchemy as sa

from mistral.db.sqlalchemy import types as st


def upgrade():
    op.drop_table('tasks')
    op.drop_table('workflow_executions')
    op.drop_table('workbooks')
    op.drop_table('triggers')
    op.add_column(
        'cron_triggers_v2',
        sa.Column('workflow_params', st.JsonEncoded(), nullable=True)
    )
    op.add_column(
        'cron_triggers_v2',
        sa.Column('workflow_params_hash', sa.CHAR(length=64), nullable=True)
    )
    op.create_unique_constraint(
        None,
        'cron_triggers_v2',
        ['workflow_input_hash', 'workflow_name', 'pattern',
         'project_id', 'workflow_params_hash']
    )
