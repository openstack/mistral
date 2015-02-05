# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import hashlib
import json
import sqlalchemy as sa
from sqlalchemy.orm import relationship

from mistral.db.sqlalchemy import model_base as mb
from mistral.db.sqlalchemy import types as st


class Workbook(mb.MistralSecureModelBase):
    """Contains info about workbook (including definition in Mistral DSL)."""

    __tablename__ = 'workbooks_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
    )

    id = mb.id_column()
    name = sa.Column(sa.String(80))
    definition = sa.Column(sa.Text(), nullable=True)
    spec = sa.Column(st.JsonDictType())
    tags = sa.Column(st.JsonListType())


class Workflow(mb.MistralSecureModelBase):
    """Contains info about workflow (including definition in Mistral DSL)."""

    __tablename__ = 'workflows_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
    )

    id = mb.id_column()
    name = sa.Column(sa.String(80))
    definition = sa.Column(sa.Text(), nullable=True)
    spec = sa.Column(st.JsonDictType())
    tags = sa.Column(st.JsonListType())


class Execution(mb.MistralSecureModelBase):
    """Contains workflow execution information."""

    __tablename__ = 'executions_v2'

    id = mb.id_column()
    wf_name = sa.Column(sa.String(80))
    wf_spec = sa.Column(st.JsonDictType())
    start_params = sa.Column(st.JsonDictType())
    state = sa.Column(sa.String(20))
    state_info = sa.Column(sa.Text(), nullable=True)
    input = sa.Column(st.JsonDictType())
    output = sa.Column(st.JsonDictType())
    context = sa.Column(st.JsonDictType())
    # Can't use ForeignKey constraint here because SqlAlchemy will detect
    # a circular dependency and raise an error.
    parent_task_id = sa.Column(sa.String(36))

    # TODO(nmakhotkin): It's not used now, must be fixed later.
    trust_id = sa.Column(sa.String(80))


class Task(mb.MistralSecureModelBase):
    """Contains task runtime information."""

    __tablename__ = 'tasks_v2'

    # Main properties.
    id = mb.id_column()
    name = sa.Column(sa.String(80))
    wf_name = sa.Column(sa.String(80))
    spec = sa.Column(st.JsonDictType())
    action_spec = sa.Column(st.JsonDictType())
    state = sa.Column(sa.String(20))
    tags = sa.Column(st.JsonListType())

    # Data Flow properties.
    in_context = sa.Column(st.JsonDictType())
    input = sa.Column(st.JsonDictType())
    output = sa.Column(st.JsonDictType())

    # Runtime context like iteration_no of a repeater.
    # Effectively internal engine properties which will be used to determine
    # execution of a task.
    runtime_context = sa.Column(st.JsonDictType())

    # Relations.
    execution_id = sa.Column(sa.String(36), sa.ForeignKey('executions_v2.id'))
    execution = relationship('Execution', backref="tasks", lazy='joined')

    def to_dict(self):
        d = super(Task, self).to_dict()

        d['result'] = json.dumps(
            d['output'].get('task', {}).get(d['name'], {})
            if d['output'] else {}
        )

        return d


class DelayedCall(mb.MistralModelBase):
    """Contains info about delayed calls."""

    __tablename__ = 'delayed_calls_v2'

    id = mb.id_column()
    factory_method_path = sa.Column(sa.String(200), nullable=True)
    target_method_name = sa.Column(sa.String(80), nullable=False)
    method_arguments = sa.Column(st.JsonDictType())
    serializers = sa.Column(st.JsonDictType())
    auth_context = sa.Column(st.JsonDictType())
    execution_time = sa.Column(sa.DateTime, nullable=False)


class Action(mb.MistralSecureModelBase):
    """Contains info about registered Actions."""

    __tablename__ = 'actions_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
    )

    # Main properties.
    id = mb.id_column()
    name = sa.Column(sa.String(200))
    description = sa.Column(sa.Text())
    tags = sa.Column(st.JsonListType())
    input = sa.Column(sa.Text())

    # Ad-hoc action properties.
    definition = sa.Column(sa.Text(), nullable=True)
    spec = sa.Column(st.JsonDictType())

    # Service properties.
    action_class = sa.Column(sa.String(200))
    attributes = sa.Column(st.JsonDictType())
    is_system = sa.Column(sa.Boolean())


class Environment(mb.MistralSecureModelBase):
    """Contains environment variables for workflow execution."""

    __tablename__ = 'environments_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
    )

    # Main properties.
    id = mb.id_column()
    name = sa.Column(sa.String(200))
    description = sa.Column(sa.Text())
    variables = sa.Column(st.JsonDictType())


def _calc_workflow_input_hash(context):
    d = context.current_parameters['workflow_input'] or {}

    return hashlib.sha256(json.dumps(sorted(d.items()))).hexdigest()


class CronTrigger(mb.MistralSecureModelBase):
    """Contains info about cron triggers."""

    __tablename__ = 'cron_triggers_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
        sa.UniqueConstraint(
            'workflow_input_hash', 'workflow_name', 'pattern', 'project_id'
        )
    )

    id = mb.id_column()
    name = sa.Column(sa.String(200))
    pattern = sa.Column(sa.String(100))
    next_execution_time = sa.Column(sa.DateTime, nullable=False)
    workflow_name = sa.Column(sa.String(80))

    workflow_id = sa.Column(sa.String(36), sa.ForeignKey('workflows_v2.id'))
    workflow = relationship('Workflow', lazy='joined')

    workflow_input = sa.Column(st.JsonDictType())
    workflow_input_hash = sa.Column(
        sa.CHAR(64),
        default=_calc_workflow_input_hash
    )

    trust_id = sa.Column(sa.String(80))

    def to_dict(self):
        d = super(CronTrigger, self).to_dict()

        mb.datetime_to_str(d, 'next_execution_time')

        return d


# Register all hooks related to secure models.
mb.register_secure_model_hooks()
