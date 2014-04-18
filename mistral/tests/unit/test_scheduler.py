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
from mistral.tests import base


SAMPLE_TRIGGER = {
    "id": "123",
    "name": "test_trigger",
    "patter": "* *",
    "next_execution_time": timeutils.utcnow(),
    "workbook_name": "My workbook"
}


class SchedulerTest(base.DbTestCase):
    def setUp(self):
        super(SchedulerTest, self).setUp()
        self.wb_name = "My workbook"

    def test_trigger_create_and_update(self):
        base = datetime(2010, 8, 25)
        next_trigger = datetime(2010, 8, 25, 0, 5)
        trigger = s.create_trigger("test", "*/5 * * * *", self.wb_name, base)
        self.assertEqual(trigger['next_execution_time'], next_trigger)

        trigger = s.set_next_execution_time(trigger)
        next_trigger = datetime(2010, 8, 25, 0, 10)
        self.assertEqual(trigger['next_execution_time'], next_trigger)

    def test_get_trigger_in_correct_orders(self):
        base = datetime(2010, 8, 25)
        s.create_trigger("test1", "*/5 * * * *", self.wb_name, base)
        base = datetime(2010, 8, 22)
        s.create_trigger("test2", "*/5 * * * *", self.wb_name, base)
        base = datetime(2010, 9, 21)
        s.create_trigger("test3", "*/5 * * * *", self.wb_name, base)
        base = datetime.now() + timedelta(0, 50)
        s.create_trigger("test4", "*/5 * * * *", self.wb_name, base)
        triggersName = [e['name'] for e in s.get_next_triggers()]

        self.assertEqual(triggersName, ["test2", "test1", "test3"])
