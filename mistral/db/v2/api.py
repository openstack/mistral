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

import contextlib

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


@contextlib.contextmanager
def transaction():
    with IMPL.transaction():
        yield


# Workbooks.

def get_workbook(name):
    return IMPL.get_workbook(name)


def load_workbook(name):
    """Unlike get_workbook this method is allowed to return None."""
    return IMPL.load_workbook(name)


def get_workbooks():
    return IMPL.get_workbooks()


def create_workbook(values):
    return IMPL.create_workbook(values)


def update_workbook(name, values):
    return IMPL.update_workbook(name, values)


def create_or_update_workbook(name, values):
    return IMPL.create_or_update_workbook(name, values)


def delete_workbook(name):
    IMPL.delete_workbook(name)


def delete_workbooks(**kwargs):
    IMPL.delete_workbooks(**kwargs)

# Workflows.


def get_workflow(name):
    return IMPL.get_workflow(name)


def load_workflow(name):
    """Unlike get_workflow this method is allowed to return None."""
    return IMPL.load_workflow(name)


def get_workflows():
    return IMPL.get_workflows()


def create_workflow(values):
    return IMPL.create_workflow(values)


def update_workflow(name, values):
    return IMPL.update_workflow(name, values)


def create_or_update_workflow(name, values):
    return IMPL.create_or_update_workflow(name, values)


def delete_workflow(name):
    IMPL.delete_workflow(name)


def delete_workflows(**kwargs):
    IMPL.delete_workflows(**kwargs)


# Executions.

def get_execution(id):
    return IMPL.get_execution(id)


def load_execution(name):
    """Unlike get_execution this method is allowed to return None."""
    return IMPL.load_execution(name)


def get_executions(**kwargs):
    return IMPL.get_executions(**kwargs)


def ensure_execution_exists(id):
    return IMPL.ensure_execution_exists(id)


def create_execution(values):
    return IMPL.create_execution(values)


def update_execution(id, values):
    return IMPL.update_execution(id, values)


def create_or_update_execution(id, values):
    return IMPL.create_or_update_execution(id, values)


def delete_execution(id):
    return IMPL.delete_execution(id)


def delete_executions(**kwargs):
    IMPL.delete_executions(**kwargs)


# Tasks.

def get_task(id):
    return IMPL.get_task(id)


def load_task(name):
    """Unlike get_task this method is allowed to return None."""
    return IMPL.load_task(name)


def get_tasks(**kwargs):
    return IMPL.get_tasks(**kwargs)


def create_task(values):
    return IMPL.create_task(values)


def update_task(id, values):
    return IMPL.update_task(id, values)


def create_or_update_task(id, values):
    return IMPL.create_or_update_task(id, values)


def delete_task(id):
    return IMPL.delete_task(id)


def delete_tasks(**kwargs):
    return IMPL.delete_tasks(**kwargs)


# Delayed calls.


def create_delayed_call(values):
    return IMPL.create_delayed_call(values)


def delete_delayed_call(id):
    return IMPL.delete_delayed_call(id)


def get_delayed_calls_to_start(time):
    return IMPL.get_delayed_calls_to_start(time)


# Actions.

def get_action(name):
    return IMPL.get_action(name)


def load_action(name):
    """Unlike get_action this method is allowed to return None."""
    return IMPL.load_action(name)


def get_actions(**kwargs):
    return IMPL.get_actions(**kwargs)


def create_action(values):
    return IMPL.create_action(values)


def update_action(name, values):
    return IMPL.update_action(name, values)


def create_or_update_action(name, values):
    return IMPL.create_or_update_action(name, values)


def delete_action(name):
    return IMPL.delete_action(name)


def delete_actions(**kwargs):
    return IMPL.delete_actions(**kwargs)


# Cron triggers.

def get_cron_trigger(name):
    return IMPL.get_cron_trigger(name)


def load_cron_trigger(name):
    """Unlike get_cron_trigger this method is allowed to return None."""
    return IMPL.load_cron_trigger(name)


def get_cron_triggers(**kwargs):
    return IMPL.get_cron_triggers(**kwargs)


def get_next_cron_triggers(time):
    return IMPL.get_next_cron_triggers(time)


def create_cron_trigger(values):
    return IMPL.create_cron_trigger(values)


def update_cron_trigger(name, values):
    return IMPL.update_cron_trigger(name, values)


def create_or_update_cron_trigger(name, values):
    return IMPL.create_or_update_cron_trigger(name, values)


def delete_cron_trigger(name):
    return IMPL.delete_cron_trigger(name)


def delete_cron_triggers(**kwargs):
    return IMPL.delete_cron_triggers(**kwargs)
