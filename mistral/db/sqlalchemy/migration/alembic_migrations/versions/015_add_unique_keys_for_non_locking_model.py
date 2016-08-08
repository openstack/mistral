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

"""add_unique_keys_for_non_locking_model

Revision ID: 015
Revises: 014
Create Date: 2016-08-08 11:05:20.109380

"""

# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'delayed_calls_v2',
        sa.Column('unique_key', sa.String(length=80), nullable=True)
    )
    op.create_unique_constraint(
        None,
        'delayed_calls_v2',
        ['unique_key', 'processing']
    )

    op.add_column(
        'task_executions_v2',
        sa.Column('unique_key', sa.String(length=80), nullable=True)
    )
    op.create_unique_constraint(
        None,
        'task_executions_v2',
        ['unique_key']
    )
