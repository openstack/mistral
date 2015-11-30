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

"""cron_trigger_constraints

Revision ID: 003
Revises: 002
Create Date: 2015-05-25 13:09:50.190136

"""

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'cron_triggers_v2',
        sa.Column('first_execution_time', sa.DateTime(), nullable=True)
    )

    op.create_unique_constraint(
        None,
        'cron_triggers_v2', [
            'workflow_input_hash', 'workflow_name', 'pattern',
            'project_id', 'workflow_params_hash', 'remaining_executions',
            'first_execution_time'
        ]
    )
