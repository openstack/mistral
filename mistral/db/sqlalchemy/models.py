# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

import sqlalchemy as sa
import uuid

from mistral.db.sqlalchemy import model_base as mb
from mistral.db.sqlalchemy import types as st

## Helpers


def _generate_unicode_uuid():
    return unicode(str(uuid.uuid4()))


def _id_column():
    return sa.Column(sa.String(36),
                     primary_key=True,
                     default=_generate_unicode_uuid)


class Event(mb.MistralBase):
    """Contains all info about event."""

    __tablename__ = 'events'

    __table_args__ = (
        sa.UniqueConstraint('name'),
    )

    id = _id_column()
    name = sa.Column(sa.String(80), nullable=False)
    pattern = sa.Column(sa.String(20), nullable=False)
    next_execution_time = sa.Column(sa.DateTime, nullable=False)
    workbook_name = sa.Column(sa.String(80), nullable=False)


class WorkflowExecution(mb.MistralBase):
    """Contains info about particular workflow execution."""

    __tablename__ = 'workflow_executions'

    id = _id_column()
    workbook_name = sa.Column(sa.String(80))
    target_task = sa.Column(sa.String(80))
    state = sa.Column(sa.String(20))


class Workbook(mb.MistralBase):
    """Contains info about workbook (including definition in Mistral DSL)."""

    __tablename__ = 'workbooks'

    __table_args__ = (
        sa.UniqueConstraint('name'),
    )

    id = _id_column()
    name = sa.Column(sa.String(80), primary_key=True)
    definition = sa.Column(sa.String(), nullable=True)
    description = sa.Column(sa.String())
    tags = sa.Column(st.JsonListType())
    scope = sa.Column(sa.String())
    project_id = sa.Column(sa.String())
    trust_id = sa.Column(sa.String())


class Task(mb.MistralBase):
    """Contains info about particular task."""

    __tablename__ = 'tasks'

    id = _id_column()
    name = sa.Column(sa.String(80))
    dependencies = sa.Column(st.JsonListType())
    workbook_name = sa.Column(sa.String(80))
    execution_id = sa.Column(sa.String(36))
    description = sa.Column(sa.String())
    task_dsl = sa.Column(st.JsonDictType())
    service_dsl = sa.Column(st.JsonDictType())
    state = sa.Column(sa.String(20))
    tags = sa.Column(st.JsonListType())
