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

"""Add has_next_tasks and error_handled to task execution.

Revision ID: 032
Revises: 031
Create Date: 2019-04-16 13:42:12.123412

"""

# revision identifiers, used by Alembic.
revision = '032'
down_revision = '031'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'task_executions_v2',
        sa.Column('has_next_tasks', sa.Boolean(), nullable=True)
    )
    op.add_column(
        'task_executions_v2',
        sa.Column('error_handled', sa.Boolean(), nullable=True)
    )
