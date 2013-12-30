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

import mock
import pkg_resources as pkg

from mistralclient.api import client

from demo_app import version

MISTRAL_URL = "http://localhost:8989/v1"
client.Client.authenticate = mock.MagicMock(return_value=(MISTRAL_URL,
                                                          "", "", ""))
CLIENT = client.Client(mistral_url=MISTRAL_URL,
                       project_name="mistral_demo")


WB_NAME = "myWorkbook"
TARGET_TASK = "task4"


def upload_workbook():
    try:
        CLIENT.workbooks.get(WB_NAME)
    except:
        CLIENT.workbooks.create(WB_NAME,
                                description="My test workbook",
                                tags=["test"])
    print("Uploading workbook definition...\n")
    definition = get_workbook_definition()
    CLIENT.workbooks.upload_definition(WB_NAME, definition)
    print definition
    print("\nUploaded.")


def get_workbook_definition():
    return open(pkg.resource_filename(version.version_info.package,
                                      "demo.yaml")).read()


def start_execution():
    import threading
    t = threading.Thread(target=CLIENT.executions.create,
                         kwargs={'workbook_name': WB_NAME,
                                 'target_task': TARGET_TASK})
    t.start()
    return "accepted"
