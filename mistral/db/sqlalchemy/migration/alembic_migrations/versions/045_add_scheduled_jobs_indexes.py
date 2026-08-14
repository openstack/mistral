# Copyright 2026 OpenStack Foundation.
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

"""Add indexes to scheduled_jobs_v2.

Revision ID: 045
Revises: 044
Create Date: 2026-07-10 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '045'
down_revision = '044'


def upgrade():
    op.create_index(
        'scheduled_jobs_v2_execute_at_captured_at',
        'scheduled_jobs_v2',
        ['execute_at', 'captured_at'],
        unique=False
    )

    op.create_index(
        'scheduled_jobs_v2_key',
        'scheduled_jobs_v2',
        ['key'],
        unique=False
    )
