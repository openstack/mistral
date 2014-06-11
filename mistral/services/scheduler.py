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

from croniter import croniter
import datetime
from mistral.db import api as db_api
from mistral import dsl_parser as parser


def get_next_triggers():
    return db_api.get_next_triggers(datetime.datetime.now() +
                                    datetime.timedelta(0, 2))


def set_next_execution_time(trigger):
    base = trigger['next_execution_time']
    cron = croniter(trigger['pattern'], base)

    return db_api.trigger_update(trigger['id'], {
        'next_execution_time': cron.get_next(datetime.datetime)
    })


def _get_next_execution_time(pattern, start_time):
    return croniter(pattern, start_time).get_next(datetime.datetime)


def create_trigger(name, pattern, workbook_name, start_time=None):
    if not start_time:
        start_time = datetime.datetime.now()

    return db_api.trigger_create({
        "name": name,
        "pattern": pattern,
        "next_execution_time": _get_next_execution_time(pattern, start_time),
        "workbook_name": workbook_name
    })


def create_associated_triggers(db_workbook):
    if not db_workbook['definition']:
        return

    workbook = parser.get_workbook(db_workbook['definition'])
    triggers = workbook.get_triggers()

    # Prepare all triggers data in advance to make db transaction shorter.
    db_triggers = []

    for e in triggers:
        pattern = e['parameters']['cron-pattern']
        next_time = _get_next_execution_time(pattern, datetime.datetime.now())
        db_triggers.append({
            "name": e['name'],
            "pattern": pattern,
            "next_execution_time": next_time,
            "workbook_name": db_workbook['name']
        })

    db_api.start_tx()

    try:
        for e in db_triggers:
            db_api.trigger_create(e)

        db_api.commit_tx()
    finally:
        db_api.end_tx()
