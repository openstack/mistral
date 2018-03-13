# Copyright 2017 OpenStack Foundation.
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

"""Fix length task name

Revision ID: 025
Revises: 024
Create Date: 2017-12-16 23:25:04.666777

"""

# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # https://dev.mysql.com/doc/refman/5.6/en/innodb-restrictions.html
    op.alter_column('task_executions_v2', 'unique_key', type_=sa.String(255))
    op.alter_column('named_locks', 'name', type_=sa.String(255))
