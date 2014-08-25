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

from oslo.db import api as db_api

from mistral.openstack.common import log as logging

_BACKEND_MAPPING = {
    'sqlalchemy': 'mistral.db.v2.sqlalchemy.api',
}

IMPL = db_api.DBAPI('sqlalchemy', backend_mapping=_BACKEND_MAPPING)
LOG = logging.getLogger(__name__)


def setup_db():
    IMPL.setup_db()


def drop_db():
    IMPL.drop_db()


# Transaction control.


def start_tx():
    IMPL.start_tx()


def commit_tx():
    IMPL.commit_tx()


def rollback_tx():
    IMPL.rollback_tx()


def end_tx():
    IMPL.end_tx()


# Workbooks.

def get_workbook(name):
    return IMPL.get_workbook(name)


def get_workbooks():
    return IMPL.get_workbooks()


def create_workbook(values):
    return IMPL.create_workbook(values)


def update_workbook(name, values):
    return IMPL.update_workbook(name, values)


def delete_workbook(name):
    IMPL.delete_workbook(name)


# Workflows.


def get_workflow(name):
    return IMPL.get_workflow(name)


def get_workflows():
    return IMPL.get_workflows()


def create_workflow(values):
    return IMPL.create_workflow(values)


def update_workflow(name, values):
    return IMPL.update_workflow(name, values)


def delete_workflow(name):
    IMPL.delete_workflow(name)


# Executions.

def get_execution(id):
    return IMPL.get_execution(id)


def get_executions(**kwargs):
    return IMPL.get_executions(**kwargs)


def ensure_execution_exists(id):
    return IMPL.ensure_execution_exists(id)


def create_execution(values):
    return IMPL.create_execution(values)


def update_execution(id, values):
    return IMPL.update_execution(id, values)


def delete_execution(id):
    return IMPL.delete_execution(id)


# Tasks.

def get_task(id):
    return IMPL.get_task(id)


def get_tasks(**kwargs):
    return IMPL.get_tasks(**kwargs)


def create_task(values):
    return IMPL.create_task(values)


def update_task(id, values):
    return IMPL.update_task(id, values)


def delete_task(id):
    return IMPL.delete_task(id)
