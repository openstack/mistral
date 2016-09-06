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

"""add a Boolean column 'processed' to the table  delayed_calls_v2

Revision ID: 006
Revises: 005
Create Date: 2015-08-09 09:44:38.289271

"""

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        'delayed_calls_v2',
        sa.Column('processing', sa.Boolean, default=False, nullable=False)
    )
