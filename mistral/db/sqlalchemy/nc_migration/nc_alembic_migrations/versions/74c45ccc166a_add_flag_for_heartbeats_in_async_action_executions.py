# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Add flag for heartbeats in async action executions

Revision ID: 74c45ccc166a
Revises: 2b78d2e173be
Create Date: 2022-07-15 01:43:55.201060

"""

# revision identifiers, used by Alembic.
revision = '74c45ccc166a'
down_revision = '2b78d2e173be'

from alembic import op
from mistral.db.utils import column_exists
import sqlalchemy as sa


def upgrade():
    if not column_exists('action_executions_v2', 'async_heartbeats_enabled'):
        op.add_column(
            'action_executions_v2',
            sa.Column(
                'async_heartbeats_enabled',
                sa.Boolean(),
                nullable=True
            )
        )
