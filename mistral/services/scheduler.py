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
from datetime import datetime
from datetime import timedelta
import mistral.db.api
from mistral import dsl


def get_next_events():
    return mistral.db.api.get_next_events(datetime.now() + timedelta(0, 2))


def set_next_execution_time(event):
    base = event['next_execution_time']
    cron = croniter(event['pattern'], base)

    return mistral.db.api.event_update(event['id'], {
        'next_execution_time': cron.get_next(datetime)
    })


def _get_next_execution_time(pattern, start_time):
    return croniter(pattern, start_time).get_next(datetime)


def create_event(name, pattern, workbook_name, start_time=None):
    if not start_time:
        start_time = datetime.now()

    return mistral.db.api.event_create({
        "name": name,
        "pattern": pattern,
        "next_execution_time": _get_next_execution_time(pattern, start_time),
        "workbook_name": workbook_name
    })


def create_associated_events(workbook):
    if not workbook['definition']:
        return

    parser = dsl.Parser(workbook['definition'])
    dsl_events = parser.get_events()

    # Prepare all events data in advance to make db transaction shorter.
    events = []

    for e in dsl_events:
        pattern = e['parameters']['cron-pattern']
        next_time = _get_next_execution_time(pattern, datetime.now())
        events.append({
            "name": e['name'],
            "pattern": pattern,
            "next_execution_time": next_time,
            "workbook_name": workbook['name']
        })

    mistral.db.api.start_tx()

    try:
        for e in events:
            mistral.db.api.event_create(e)

        mistral.db.api.commit_tx()
    finally:
        mistral.db.api.end_tx()
