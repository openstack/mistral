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

"""Change scheduler schema.

Revision ID: 019
Revises: 018
Create Date: 2016-08-17 17:54:51.952949

"""

# revision identifiers, used by Alembic.
revision = '019'
down_revision = '018'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


def upgrade():
    inspect = reflection.Inspector.from_engine(op.get_bind())
    unique_constraints = [
        uc['name'] for uc in inspect.get_unique_constraints('delayed_calls_v2')
    ]

    if 'delayed_calls_v2_processing_execution_time' in unique_constraints:
        op.drop_index(
            'delayed_calls_v2_processing_execution_time',
            table_name='delayed_calls_v2'
        )

    if 'unique_key' in unique_constraints:
        op.drop_index('unique_key', table_name='delayed_calls_v2')

    op.drop_column('delayed_calls_v2', 'unique_key')

    op.add_column(
        'delayed_calls_v2',
        sa.Column('key', sa.String(length=250), nullable=True)
    )
    op.create_index(
        'delayed_calls_v2_execution_time',
        'delayed_calls_v2',
        ['execution_time'],
        unique=False
    )
