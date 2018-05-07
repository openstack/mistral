# Copyright 2018 OpenStack Foundation.
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

"""Add last_heartbeat to action execution

Revision ID: 027
Revises: 026
Create Date: 2018-09-05 16:49:50.342349

"""

# revision identifiers, used by Alembic.
revision = '027'
down_revision = '026'

from alembic import op
import datetime
from mistral import utils
from oslo_config import cfg
from sqlalchemy import Column, DateTime, Boolean

CONF = cfg.CONF


def upgrade():
    op.add_column(
        'action_executions_v2',
        Column(
            'last_heartbeat',
            DateTime,
            default=lambda: utils.utc_now_sec() + datetime.timedelta(
                seconds=CONF.action_heartbeat.first_heartbeat_timeout
            )
        )
    )
    op.add_column(
        'action_executions_v2',
        Column('is_sync', Boolean, default=None, nullable=True)
    )
