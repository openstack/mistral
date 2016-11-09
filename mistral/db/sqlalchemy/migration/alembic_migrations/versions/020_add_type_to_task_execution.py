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

"""add type to task execution

Revision ID: 020
Revises: 019
Create Date: 2016-10-05 13:24:52.911011

"""

# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.add_column(
        'task_executions_v2',
        sa.Column('type', sa.String(length=10), nullable=True)
    )
