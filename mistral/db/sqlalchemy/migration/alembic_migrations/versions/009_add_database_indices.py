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

"""Add database indices

Revision ID: 009
Revises: 008
Create Date: 2015-11-25 19:06:14.975474

"""

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'

from alembic import op
from sqlalchemy.engine import reflection


def upgrade():

    inspector = reflection.Inspector.from_engine(op.get_bind())

    op.create_index(
        'action_definitions_v2_action_class',
        'action_definitions_v2',
        ['action_class'],
        unique=False
    )

    op.create_index(
        'action_definitions_v2_is_system',
        'action_definitions_v2',
        ['is_system'],
        unique=False
    )

    op.create_index(
        'action_definitions_v2_project_id',
        'action_definitions_v2',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'action_definitions_v2_scope',
        'action_definitions_v2',
        ['scope'],
        unique=False
    )

    op.create_index(
        'cron_triggers_v2_next_execution_time',
        'cron_triggers_v2',
        ['next_execution_time'],
        unique=False
    )

    op.create_index(
        'cron_triggers_v2_project_id',
        'cron_triggers_v2',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'cron_triggers_v2_scope',
        'cron_triggers_v2',
        ['scope'],
        unique=False
    )

    op.create_index(
        'cron_triggers_v2_workflow_name',
        'cron_triggers_v2',
        ['workflow_name'],
        unique=False
    )

    cron_v2_constrs = [uc['name'] for uc in
                       inspector.get_unique_constraints('cron_triggers_v2')]
    if ('cron_triggers_v2_workflow_input_hash_workflow_name_pattern__key' in
            cron_v2_constrs):
        op.drop_constraint(
            'cron_triggers_v2_workflow_input_hash_workflow_name_pattern__key',
            'cron_triggers_v2',
            type_='unique'
        )

    if ('cron_triggers_v2_workflow_input_hash_workflow_name_pattern_key1' in
            cron_v2_constrs):
        op.drop_constraint(
            'cron_triggers_v2_workflow_input_hash_workflow_name_pattern_key1',
            'cron_triggers_v2',
            type_='unique'
        )

    op.create_index(
        'delayed_calls_v2_processing_execution_time',
        'delayed_calls_v2',
        ['processing', 'execution_time'],
        unique=False
    )

    op.create_index(
        'environments_v2_name',
        'environments_v2',
        ['name'],
        unique=False
    )

    op.create_index(
        'environments_v2_project_id',
        'environments_v2',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'environments_v2_scope',
        'environments_v2',
        ['scope'],
        unique=False
    )

    op.create_index(
        'executions_v2_project_id',
        'executions_v2',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'executions_v2_scope',
        'executions_v2',
        ['scope'],
        unique=False
    )

    op.create_index(
        'executions_v2_state',
        'executions_v2',
        ['state'],
        unique=False
    )

    op.create_index(
        'executions_v2_task_execution_id',
        'executions_v2',
        ['task_execution_id'],
        unique=False
    )

    op.create_index(
        'executions_v2_type',
        'executions_v2',
        ['type'],
        unique=False
    )

    op.create_index(
        'executions_v2_updated_at',
        'executions_v2',
        ['updated_at'],
        unique=False
    )

    op.create_index(
        'executions_v2_workflow_execution_id',
        'executions_v2',
        ['workflow_execution_id'],
        unique=False
    )

    op.create_index(
        'workbooks_v2_project_id',
        'workbooks_v2',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'workbooks_v2_scope',
        'workbooks_v2',
        ['scope'],
        unique=False
    )

    op.create_index(
        'workflow_definitions_v2_is_system',
        'workflow_definitions_v2',
        ['is_system'],
        unique=False
    )

    op.create_index(
        'workflow_definitions_v2_project_id',
        'workflow_definitions_v2',
        ['project_id'],
        unique=False
    )

    op.create_index(
        'workflow_definitions_v2_scope',
        'workflow_definitions_v2',
        ['scope'],
        unique=False
    )
