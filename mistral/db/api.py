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

# TODO: replace this module later with a real implementation
from mistral.openstack.common.db import api as db_api
from mistral.openstack.common import log as logging

# Workbooks

_BACKEND_MAPPING = {
    'sqlalchemy': 'mistral.db.sqlalchemy.api',
}

IMPL = db_api.DBAPI(backend_mapping=_BACKEND_MAPPING)
LOG = logging.getLogger(__name__)


def setup_db():
    IMPL.setup_db()


def drop_db():
    IMPL.drop_db()


# Workbook

def workbook_get(name):
    return {}


def workbook_create(values):
    return values


def workbook_update(name, values):
    return values


def workbook_delete(name):
    pass


def workbooks_get():
    return [{}]


def workbook_definition_get(workbook_name):
    return ""


def workbook_definition_put(workbook_name, text):
    return text


# Executions


def execution_get(workbook_name, id):
    return {}


def execution_create(workbook_name, values):
    return values


def execution_update(workbook_name, id, values):
    return values


def execution_delete(workbook_name, id):
    pass


def executions_get(workbook_name):
    return [{}]


# Tasks

def task_get(workbook_name, execution_id, id):
    return {}


def task_create(workbook_name, execution_id, values):
    return values


def task_update(workbook_name, execution_id, id, values):
    return values


def task_delete(workbook_name, execution_id, id):
    pass


def tasks_get(workbook_name, execution_id):
    return [{}]


# Listeners


def listener_get(workbook_name, id):
    return {}


def listener_create(workbook_name, values):
    values['id'] = 1

    return values


def listener_update(workbook_name, id, values):
    return values


def listener_delete(workbook_name, id):
    pass


def listeners_get(workbook_name):
    return [{}]


# Events

def event_create(values):
    return IMPL.event_create(values)


def event_update(event_id, values):
    return IMPL.event_update(event_id, values)


def get_next_events(time):
    return IMPL.get_next_events(time)
