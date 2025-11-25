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

"""Add checksum field to wf definition

Revision ID: 2b78d2e173be
Revises: e5c90eeb5dce
Create Date: 2021-11-01 15:06:02.502997

"""

# revision identifiers, used by Alembic.
revision = '2b78d2e173be'
down_revision = 'e5c90eeb5dce'

from alembic import op
from mistral.db.utils import column_exists
import sqlalchemy as sa


def upgrade():
    if not column_exists('workflow_definitions_v2', 'checksum'):
        op.add_column(
            'workflow_definitions_v2',
            sa.Column('checksum', sa.String(length=32), nullable=True)
        )
