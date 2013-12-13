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
    time = datetime.now() + timedelta(0, 2)
    return mistral.db.api.get_next_events(time)


def set_next_execution_time(event):
    base = event['next_execution_time']
    cron = croniter(event['pattern'], base)
    return mistral.db.api.event_update(event['id'], {
        'next_execution_time': cron.get_next(datetime)
    })


def create_event(name, pattern, workbook_name, start_time=None):
    if not start_time:
        start_time = datetime.now()
    cron = croniter(pattern, start_time)
    next_execution_time = cron.get_next(datetime)
    return mistral.db.api.event_create({
        "name": name,
        "pattern": pattern,
        "next_execution_time": next_execution_time,
        "workbook_name": workbook_name
    })


def create_associated_events(workbook):
    if not workbook.definition:
        return
    parser = dsl.Parser(workbook.definition)
    events = parser.get_events()
    for e in events:
        create_event(e['name'],
                     e['parameters']['cron-pattern'],
                     workbook.name)
