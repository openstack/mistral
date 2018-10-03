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

"""Add started_at and finished_at to task execution

Revision ID: 031
Revises: 030
Create Date: 2018-10-03 20:09:45.582597

"""

# revision identifiers, used by Alembic.
revision = '031'
down_revision = '030'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'task_executions_v2',
        sa.Column('started_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'task_executions_v2',
        sa.Column('finished_at', sa.DateTime(), nullable=True)
    )
