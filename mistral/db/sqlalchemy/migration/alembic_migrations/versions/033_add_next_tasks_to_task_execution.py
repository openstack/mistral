# Copyright 2019 OpenStack Foundation.
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

"""Add next_tasks to task execution.

Revision ID: 033
Revises: 032
Create Date: 2019-06-06 13:42:12.123412

"""

# revision identifiers, used by Alembic.
revision = '033'
down_revision = '032'

from alembic import op
import sqlalchemy as sa

from mistral.db.sqlalchemy import types as st


def upgrade():
    op.add_column(
        'task_executions_v2',
        sa.Column('next_tasks', st.JsonListType(), nullable=True)
    )
