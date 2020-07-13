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

"""Delete delayed calls with key=NULL.

Revision ID: 038
Revises: 037
Create Date: 2020-7-13 13:20:00

"""

# revision identifiers, used by Alembic.

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column

revision = '038'
down_revision = '037'


def upgrade():
    # See https://bugs.launchpad.net/mistral/+bug/1861988.
    # Due to this bug there may be redundant delayed calls in DB.
    # We need to delete all rows where the "key" column is None.
    session = sa.orm.Session(bind=op.get_bind())

    delayed_calls = table('delayed_calls_v2', column('key'))

    with session.begin(subtransactions=True):
        session.execute(
            delayed_calls.delete().where(delayed_calls.c.key==None)  # noqa
        )

    session.commit()
