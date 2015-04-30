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
from sqlalchemy import event
from sqlalchemy.orm import backref
from sqlalchemy.orm import relationship

from mistral.db.sqlalchemy import model_base as mb
from mistral.db.sqlalchemy import types as st
from mistral import utils


# Definition objects.


class Definition(mb.MistralSecureModelBase):
    __abstract__ = True

    id = mb.id_column()
    name = sa.Column(sa.String(80))
    definition = sa.Column(sa.Text(), nullable=True)
    spec = sa.Column(st.JsonDictType())
    tags = sa.Column(st.JsonListType())


# There's no WorkbookExecution so we safely omit "Definition" in the name.
class Workbook(Definition):
    """Contains info about workbook (including definition in Mistral DSL)."""

    __tablename__ = 'workbooks_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
    )


class WorkflowDefinition(Definition):
    """Contains info about workflow (including definition in Mistral DSL)."""

    __tablename__ = 'workflow_definitions_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
    )


class ActionDefinition(Definition):
    """Contains info about registered Actions."""

    __tablename__ = 'action_definitions_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
    )

    # Main properties.
    description = sa.Column(sa.Text())
    input = sa.Column(sa.Text())

    # Service properties.
    action_class = sa.Column(sa.String(200))
    attributes = sa.Column(st.JsonDictType())
    is_system = sa.Column(sa.Boolean())


# Execution objects.

class Execution(mb.MistralSecureModelBase):
    """Abstract execution object."""

    __tablename__ = 'executions_v2'

    type = sa.Column(sa.String(50))

    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': 'execution'
    }

    # Main properties.
    id = mb.id_column()
    name = sa.Column(sa.String(80))

    workflow_name = sa.Column(sa.String(80))
    spec = sa.Column(st.JsonDictType())
    state = sa.Column(sa.String(20))
    state_info = sa.Column(sa.String(1024), nullable=True)
    tags = sa.Column(st.JsonListType())

    # Runtime context like iteration_no of a repeater.
    # Effectively internal engine properties which will be used to determine
    # execution of a task.
    runtime_context = sa.Column(st.JsonDictType())


class ActionExecution(Execution):
    """Contains action execution information."""

    __mapper_args__ = {
        'polymorphic_identity': 'action_execution'
    }

    # Main properties.
    accepted = sa.Column(sa.Boolean(), default=False)
    input = sa.Column(st.JsonDictType(), nullable=True)

    output = sa.orm.deferred(sa.Column(st.JsonLongDictType(), nullable=True))


class WorkflowExecution(ActionExecution):
    """Contains workflow execution information."""

    __mapper_args__ = {
        'polymorphic_identity': 'workflow_execution'
    }

    # Main properties.
    params = sa.Column(st.JsonDictType())

    # TODO(rakhmerov): We need to get rid of this field at all.
    context = sa.Column(st.JsonDictType())


class TaskExecution(Execution):
    """Contains task runtime information."""

    __mapper_args__ = {
        'polymorphic_identity': 'task_execution'
    }

    # Main properties.
    action_spec = sa.Column(st.JsonDictType())

    # Whether the task is fully processed (publishing and calculating commands
    # after it). It allows to simplify workflow controller implementations
    # significantly.
    processed = sa.Column(sa.BOOLEAN, default=False)

    # Data Flow properties.
    in_context = sa.Column(st.JsonLongDictType())
    published = sa.Column(st.JsonDictType())


for cls in utils.iter_subclasses(Execution):
    event.listen(
        # Catch and trim Execution.state_info to always fit allocated size.
        cls.state_info,
        'set',
        lambda t, v, o, i: utils.cut(v, 1020),
        retval=True
    )

# Many-to-one for 'Execution' and 'TaskExecution'.

Execution.task_execution_id = sa.Column(
    sa.String(36),
    sa.ForeignKey(TaskExecution.id),
    nullable=True
)

TaskExecution.executions = relationship(
    Execution,
    backref=backref('task_execution', remote_side=[TaskExecution.id]),
    cascade='all, delete-orphan',
    foreign_keys=Execution.task_execution_id,
    lazy='select'
)

# Many-to-one for 'TaskExecution' and 'WorkflowExecution'.

TaskExecution.workflow_execution_id = sa.Column(
    sa.String(36),
    sa.ForeignKey(WorkflowExecution.id)
)

WorkflowExecution.task_executions = relationship(
    TaskExecution,
    backref=backref('workflow_execution', remote_side=[WorkflowExecution.id]),
    cascade='all, delete-orphan',
    foreign_keys=TaskExecution.workflow_execution_id,
    lazy='select'
)


# Other objects.


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


def _get_hash_function_by(column_name):
    def calc_hash(context):
        d = context.current_parameters[column_name] or {}

        return hashlib.sha256(json.dumps(sorted(d.items()))).hexdigest()

    return calc_hash


class CronTrigger(mb.MistralSecureModelBase):
    """Contains info about cron triggers."""

    __tablename__ = 'cron_triggers_v2'

    __table_args__ = (
        sa.UniqueConstraint('name', 'project_id'),
        sa.UniqueConstraint(
            'workflow_input_hash', 'workflow_name', 'pattern', 'project_id',
            'workflow_params_hash'
        )
    )

    id = mb.id_column()
    name = sa.Column(sa.String(200))
    pattern = sa.Column(sa.String(100))
    next_execution_time = sa.Column(sa.DateTime, nullable=False)
    workflow_name = sa.Column(sa.String(80))
    remaining_executions = sa.Column(sa.Integer)

    workflow_id = sa.Column(
        sa.String(36),
        sa.ForeignKey(WorkflowDefinition.id)
    )
    workflow = relationship('WorkflowDefinition', lazy='joined')

    workflow_params = sa.Column(st.JsonDictType())
    workflow_params_hash = sa.Column(
        sa.CHAR(64),
        default=_get_hash_function_by('workflow_params')
    )
    workflow_input = sa.Column(st.JsonDictType())
    workflow_input_hash = sa.Column(
        sa.CHAR(64),
        default=_get_hash_function_by('workflow_input')
    )

    trust_id = sa.Column(sa.String(80))

    def to_dict(self):
        d = super(CronTrigger, self).to_dict()

        mb.datetime_to_str(d, 'next_execution_time')

        return d


# Register all hooks related to secure models.
mb.register_secure_model_hooks()
