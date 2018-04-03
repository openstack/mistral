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

"""Optimize task expression function

Revision ID: 026
Revises: 025
Create Date: 2018-22-03 15:23:04.904251

"""

# revision identifiers, used by Alembic.
revision = '026'
down_revision = '025'

from alembic import op


def upgrade():
    op.create_index('action_executions_v2_task_execution_id',
                    'action_executions_v2',
                    ['task_execution_id'])
    op.create_index('workflow_executions_v2_task_execution_id',
                    'workflow_executions_v2',
                    ['task_execution_id'])
