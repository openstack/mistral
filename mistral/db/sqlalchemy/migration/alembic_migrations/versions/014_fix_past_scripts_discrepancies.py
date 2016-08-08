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

"""fix_past_scripts_discrepancies

Revision ID: 014
Revises: 013
Create Date: 2016-08-07 13:12:34.958845

"""

# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013'

from alembic import op
from sqlalchemy.dialects import mysql
from sqlalchemy.engine import reflection


def upgrade():

    inspect = reflection.Inspector.from_engine(op.get_bind())
    ct_unique_constraints = [
        uc['name'] for uc in inspect.get_unique_constraints('cron_triggers_v2')
    ]

    # unique constraint was added in 001, 002 and 003 with slight variations
    # without deleting the previous ones.
    # here we try to delete all three in case they exist
    if 'workflow_input_hash' in ct_unique_constraints:
        op.drop_index('workflow_input_hash', table_name='cron_triggers_v2')
    if 'workflow_input_hash_2' in ct_unique_constraints:
        op.drop_index('workflow_input_hash_2', table_name='cron_triggers_v2')
    if 'workflow_input_hash_3' in ct_unique_constraints:
        op.drop_index('workflow_input_hash_3', table_name='cron_triggers_v2')

    # create the correct latest unique constraint for table cron_triggers_v2
    op.create_unique_constraint(
        None,
        'cron_triggers_v2', [
            'workflow_input_hash', 'workflow_name', 'pattern',
            'project_id', 'workflow_params_hash', 'remaining_executions',
            'first_execution_time'
        ]
    )

    # column was added in 012. nullable value does not match today's model.
    op.alter_column(
        'event_triggers_v2',
        'workflow_id',
        existing_type=mysql.VARCHAR(length=36),
        nullable=True
    )

    # column was added in 010. nullable value does not match today's model
    op.alter_column(
        'resource_members_v2',
        'project_id',
        existing_type=mysql.VARCHAR(length=80),
        nullable=True
    )
