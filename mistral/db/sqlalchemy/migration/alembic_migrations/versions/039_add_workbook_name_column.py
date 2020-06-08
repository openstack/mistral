# Copyright 2020 Nokia Software.
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

"""Add 'workbook_name' column to 'action_definitions_v2'
   and 'workflow_definitions_v2'.

Revision ID: 039
Revises: 038
Create Date: 2020-09-07 10:51:20

"""

# revision identifiers, used by Alembic.

from alembic import op
import sqlalchemy as sa

revision = '039'
down_revision = '038'


def upgrade():
    op.add_column(
        'action_definitions_v2',
        sa.Column('workbook_name', sa.String(length=255), nullable=True)
    )

    op.add_column(
        'workflow_definitions_v2',
        sa.Column('workbook_name', sa.String(length=255), nullable=True)
    )
