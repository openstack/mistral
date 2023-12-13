# Copyright 2023 OpenStack Foundation.
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

"""add_checksum_to_wf_definition

Revision ID: 043
Revises: 042
Create Date: 2023-10-16 12:02:23.374515

"""

# revision identifiers, used by Alembic.
revision = '043'
down_revision = '042'

from alembic import op
from mistral.db.utils import column_exists
import sqlalchemy as sa


def upgrade():
    if not column_exists('workflow_definitions_v2', 'checksum'):
        op.add_column(
            'workflow_definitions_v2',
            sa.Column('checksum', sa.String(length=32), nullable=True)
        )
