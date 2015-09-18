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

"""Move system flag to base definition

Revision ID: 007
Revises: 006
Create Date: 2015-09-15 11:24:43.081824

"""

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'workbooks_v2',
        sa.Column('is_system', sa.Boolean(), nullable=True)
    )
    op.add_column(
        'workflow_definitions_v2',
        sa.Column('is_system', sa.Boolean(), nullable=True)
    )
