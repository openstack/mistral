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

"""add type to task execution

Revision ID: 020
Revises: 019
Create Date: 2016-10-05 13:24:52.911011

"""

# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'

from alembic import op
from mistral.db.sqlalchemy import types as st
import sqlalchemy as sa

# A simple model of the task executions table with only the fields needed for
# the migration.
task_executions = sa.Table(
    'task_executions_v2',
    sa.MetaData(),
    sa.Column('id', sa.String(36), nullable=False),
    sa.Column(
        'spec',
        st.JsonMediumDictType()
    ),
    sa.Column('type', sa.String(10), nullable=True)
)


def upgrade():

    op.add_column(
        'task_executions_v2',
        sa.Column('type', sa.String(length=10), nullable=True)
    )

    session = sa.orm.Session(bind=op.get_bind())
    values = []

    for row in session.query(task_executions):
        values.append({'id': row[0],
                       'spec': row[1]})

    with session.begin(subtransactions=True):
        for value in values:
            task_type = "ACTION"
            if "workflow" in value['spec']:
                task_type = "WORKFLOW"

            session.execute(
                task_executions.update().values(type=task_type).where(
                    task_executions.c.id == value['id']
                )
            )

    # this commit appears to be necessary
    session.commit()
