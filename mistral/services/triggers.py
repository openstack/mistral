# Copyright 2014 - Mirantis, Inc.
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

from croniter import croniter
import datetime
from oslo.config import cfg

from mistral import context
from mistral.db.v1 import api as db_api_v1
from mistral.db.v2 import api as db_api_v2
from mistral.services import trusts
from mistral.workbook import parser as spec_parser


def get_next_execution_time(pattern, start_time):
    return croniter(pattern, start_time).get_next(datetime.datetime)


# Triggers v1.

def get_next_triggers_v1():
    return db_api_v1.get_next_triggers(datetime.datetime.now() +
                                       datetime.timedelta(0, 2))


def create_trigger_v1(name, pattern, workbook_name, start_time=None):
    if not start_time:
        start_time = datetime.datetime.now()

    return db_api_v1.trigger_create({
        "name": name,
        "pattern": pattern,
        "next_execution_time": get_next_execution_time(pattern, start_time),
        "workbook_name": workbook_name
    })


def create_associated_triggers(db_workbook):
    if not db_workbook.definition:
        return

    wb_spec = spec_parser.get_workbook_spec_from_yaml(
        db_workbook.definition
    )

    triggers = wb_spec.get_triggers()

    # Prepare all triggers data in advance to make db transaction shorter.
    db_triggers = []

    for e in triggers:
        pattern = e['parameters']['cron-pattern']
        next_time = get_next_execution_time(pattern, datetime.datetime.now())
        db_triggers.append({
            "name": e['name'],
            "pattern": pattern,
            "next_execution_time": next_time,
            "workbook_name": db_workbook.name
        })

    with db_api_v1.transaction():
        for e in db_triggers:
            db_api_v1.trigger_create(e)


# Triggers v2.

def get_next_cron_triggers():
    return db_api_v2.get_next_cron_triggers(
        datetime.datetime.now() + datetime.timedelta(0, 2)
    )


def create_cron_trigger(name, pattern, workflow_name, workflow_input,
                        start_time=None):
    if not start_time:
        start_time = datetime.datetime.now()

    with db_api_v2.transaction():
        wf = db_api_v2.get_workflow(workflow_name)

        next_time = get_next_execution_time(pattern, start_time)

        values = {
            'name': name,
            'pattern': pattern,
            'next_execution_time': next_time,
            'workflow_name': workflow_name,
            'workflow_id': wf.id,
            'workflow_input': workflow_input,
            'scope': 'private'
        }

        _add_security_info(values)

        trig = db_api_v2.create_cron_trigger(values)

    return trig


def _add_security_info(values):
    if cfg.CONF.pecan.auth_enable:
        values.update({
            'trust_id': trusts.create_trust().id,
            'project_id': context.ctx().project_id
        })
