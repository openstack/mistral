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

from datetime import datetime
from datetime import timedelta

from mistral.openstack.common import timeutils

from mistral.services import scheduler as s
from mistral.tests.unit import base as test_base


SAMPLE_EVENT = {
    "id": "123",
    "name": "test_event",
    "patter": "* *",
    "next_execution_time": timeutils.utcnow(),
    "workbook_name": "My workbook"
}


class SchedulerTest(test_base.DbTestCase):
    def setUp(self):
        super(SchedulerTest, self).setUp()
        self.wb_name = "My workbook"

    def test_event_create_and_update(self):
        base = datetime(2010, 8, 25)
        next_event = datetime(2010, 8, 25, 0, 5)
        event = s.create_event("test", "*/5 * * * *", self.wb_name, base)
        self.assertEqual(event['next_execution_time'], next_event)

        event = s.set_next_execution_time(event)
        next_event = datetime(2010, 8, 25, 0, 10)
        self.assertEqual(event['next_execution_time'], next_event)

    def test_get_event_in_correct_orders(self):
        base = datetime(2010, 8, 25)
        s.create_event("test1", "*/5 * * * *", self.wb_name, base)
        base = datetime(2010, 8, 22)
        s.create_event("test2", "*/5 * * * *", self.wb_name, base)
        base = datetime(2010, 9, 21)
        s.create_event("test3", "*/5 * * * *", self.wb_name, base)
        base = datetime.now() + timedelta(0, 50)
        s.create_event("test4", "*/5 * * * *", self.wb_name, base)
        eventsName = [e['name'] for e in s.get_next_events()]

        self.assertEqual(eventsName, ["test2", "test1", "test3"])
