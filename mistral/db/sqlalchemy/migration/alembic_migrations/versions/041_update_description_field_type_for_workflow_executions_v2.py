# Copyright 2020 Nokia Software.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Update type of 'description' field for
   table 'workflow_executions_v2' to text

Revision ID: 041
Revises: 040
Create Date: 2022-04-19

"""

# revision identifiers, used by Alembic.
revision = '041'
down_revision = '040'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column(
        'workflow_executions_v2',
        column_name='description', type_=sa.Text(),
        existing_type=sa.String(length=255)
    )
