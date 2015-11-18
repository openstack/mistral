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

"""Increase size of state_info column from String to Text

Revision ID: 008
Revises: 007
Create Date: 2015-11-17 21:30:50.991290

"""

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('executions_v2', 'state_info',
                    type_=sa.Text())
