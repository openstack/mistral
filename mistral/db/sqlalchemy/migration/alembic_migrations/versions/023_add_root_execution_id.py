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

"""Add the root execution ID to the workflow execution model

Revision ID: 023
Revises: 022
Create Date: 2017-07-26 14:51:02.384729

"""

# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'workflow_executions_v2',
        sa.Column('root_execution_id', sa.String(length=80), nullable=True)
    )
