# Copyright 2018 - Extreme Networks, Inc.
# Modified in 2025 by NetCracker Technology Corp.
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

import copy

from oslo_log import log as logging

from mistral import context as auth_ctx
from mistral.db.v2 import api as db_api
from mistral.exceptions import ApplicationContextNotFoundException
from mistral.exceptions import DBEntityNotFoundError
from mistral.notifiers import base
from mistral.notifiers import notification_events as event_base


LOG = logging.getLogger(__name__)


class DefaultNotifier(base.Notifier):
    """Local notifier that process notification request."""

    def notify(self, ex_id, data, event, timestamp, publishers):
        try:
            ctx = auth_ctx.ctx()
        except ApplicationContextNotFoundException:
            ctx = None

        data['event'] = event

        with db_api.transaction():
            try:
                if event in event_base.TASKS:
                    if event_base.is_finished_event(event):
                        task_ex = db_api.get_task_execution(data['id'])
                        data['published'] = task_ex.published
                    else:
                        data['published'] = {}
                    wf_ex = db_api.get_workflow_execution(
                        data['workflow_execution_id']
                    )
                    data['workflow_execution_input'] = wf_ex.input
                if event in event_base.WORKFLOWS:
                    wf_ex = db_api.get_workflow_execution(data['id'])
                    if event_base.is_finished_event(event):
                        data['output'] = wf_ex.output
                    else:
                        data['output'] = {}
                    data['input'] = wf_ex.input
            except DBEntityNotFoundError:
                LOG.debug(
                    "Execution ID not found. {}",
                    data['id'],
                    exc_info=True
                )

        for entry in publishers:
            params = copy.deepcopy(entry)
            publisher_name = params.pop('type', None)

            if not publisher_name:
                LOG.error('Notification publisher type is not specified.')
                continue

            try:
                publisher = base.get_notification_publisher(publisher_name)
                publisher.publish(ctx, ex_id, data, event, timestamp, **params)
            except Exception:
                LOG.exception(
                    'Unable to process event for publisher "%s".',
                    publisher_name
                )
