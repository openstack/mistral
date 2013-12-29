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

from time import sleep
import threading

from demo_app.api import client


CLIENT = client.CLIENT


def start_task(**kwargs):
    thread = threading.Thread(target=finish_task, kwargs=kwargs)
    thread.start()


def finish_task(task_id, execution_id, workbook_name):
    # simulate working
    sleep(8)

    task = CLIENT.tasks.update(workbook_name, execution_id,
                               task_id, "SUCCESS")
    print("Task %s - SUCCESS" % task.name)
