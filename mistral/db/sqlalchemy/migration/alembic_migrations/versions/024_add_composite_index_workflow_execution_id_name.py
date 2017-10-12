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

"""Add database indices

Revision ID: 024
Revises: 023
Create Date: 2017-10-11 15:23:04.904251

"""

# revision identifiers, used by Alembic.
revision = '024'
down_revision = '023'

from alembic import op


def upgrade():
    op.create_index('task_executions_v2_workflow_execution_id_name',
                    'task_executions_v2',
                    ['workflow_execution_id', 'name'])
