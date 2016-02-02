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

"""add workflow id for execution

Revision ID: 011
Revises: 010
Create Date: 2016-02-02 22:29:34.672735

"""

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'executions_v2',
        sa.Column('workflow_id', sa.String(length=80), nullable=True)
    )
