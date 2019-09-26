# Copyright 2019 OpenStack Foundation.
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

"""Create scheduled jobs table.

Revision ID: 034
Revises: 033
Create Date: 2019-07-01 17:38:41.153354

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection

from mistral.db.sqlalchemy import types as st

# revision identifiers, used by Alembic.
revision = '034'
down_revision = '033'


def upgrade():
    # NOTE(rakhmerov): We have to check if the table already
    # exists and drop it, if needed. This is because the DB
    # model for scheduled jobs was released w/o a migration
    # in the first place, so for some users the table was
    # created automatically at Mistral run based on the model.
    # But the structure of the table is old so we need to
    # recreate it anyway in this migration. It's safe to drop
    # this table because it contains temporary data.
    inspect = reflection.Inspector.from_engine(op.get_bind())

    if 'scheduled_jobs_v2' in inspect.get_table_names():
        op.drop_table('scheduled_jobs_v2')

    op.create_table(
        'scheduled_jobs_v2',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_after', sa.Integer(), nullable=True),
        sa.Column(
            'target_factory_func_name',
            sa.String(length=200),
            nullable=True
        ),
        sa.Column('func_name', sa.String(length=80), nullable=True),
        sa.Column('func_args', st.JsonEncoded(), nullable=True),
        sa.Column('func_arg_serializers', st.JsonEncoded(), nullable=True),
        sa.Column('auth_ctx', st.JsonEncoded(), nullable=True),
        sa.Column('execute_at', sa.DateTime(), nullable=False),
        sa.Column('captured_at', sa.DateTime(), nullable=True),
        sa.Column('key', sa.String(length=250), nullable=True),

        sa.PrimaryKeyConstraint('id'),
    )
