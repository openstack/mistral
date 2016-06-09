# Copyright 2016 NEC Corporation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

policy_data = """{
    "admin_only": "is_admin:True",
    "admin_or_owner": "is_admin:True or project_id:%(project_id)s",
    "default": "rule:admin_or_owner",

    "action_executions:delete": "rule:admin_or_owner",
    "action_execution:create": "rule:admin_or_owner",
    "action_executions:get": "rule:admin_or_owner",
    "action_executions:list": "rule:admin_or_owner",
    "action_executions:update": "rule:admin_or_owner",

    "actions:create": "rule:admin_or_owner",
    "actions:delete": "rule:admin_or_owner",
    "actions:get": "rule:admin_or_owner",
    "actions:list": "rule:admin_or_owner",
    "actions:update": "rule:admin_or_owner",

    "cron_triggers:create": "rule:admin_or_owner",
    "cron_triggers:delete": "rule:admin_or_owner",
    "cron_triggers:get": "rule:admin_or_owner",
    "cron_triggers:list": "rule:admin_or_owner",

    "environments:create": "rule:admin_or_owner",
    "environments:delete": "rule:admin_or_owner",
    "environments:get": "rule:admin_or_owner",
    "environments:list": "rule:admin_or_owner",
    "environments:update": "rule:admin_or_owner",

    "executions:create": "rule:admin_or_owner",
    "executions:delete": "rule:admin_or_owner",
    "executions:get": "rule:admin_or_owner",
    "executions:list": "rule:admin_or_owner",
    "executions:update": "rule:admin_or_owner",

    "members:create": "rule:admin_or_owner",
    "members:delete": "rule:admin_or_owner",
    "members:get": "rule:admin_or_owner",
    "members:list": "rule:admin_or_owner",
    "members:update": "rule:admin_or_owner",

    "services:list": "rule:admin_or_owner",

    "tasks:get": "rule:admin_or_owner",
    "tasks:list": "rule:admin_or_owner",
    "tasks:update": "rule:admin_or_owner",

    "workbooks:create": "rule:admin_or_owner",
    "workbooks:delete": "rule:admin_or_owner",
    "workbooks:get": "rule:admin_or_owner",
    "workbooks:list": "rule:admin_or_owner",
    "workbooks:update": "rule:admin_or_owner",

    "workflows:create": "rule:admin_or_owner",
    "workflows:delete": "rule:admin_or_owner",
    "workflows:get": "rule:admin_or_owner",
    "workflows:list": "rule:admin_or_owner",
    "workflows:update": "rule:admin_or_owner",
}"""
