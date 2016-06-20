# Copyright 2014 - Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
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
import six

from mistral.db.v2 import api as db_api
from mistral.engine.rpc_backend import rpc
from mistral.engine import utils as eng_utils
from mistral import exceptions as exc
from mistral.services import security
from mistral.workbook import parser


def get_next_execution_time(pattern, start_time):
    return croniter(pattern, start_time).get_next(datetime.datetime)


# Triggers v2.

def get_next_cron_triggers():
    return db_api.get_next_cron_triggers(
        datetime.datetime.now() + datetime.timedelta(0, 2)
    )


def validate_cron_trigger_input(pattern, first_time, count):
    if not (first_time or pattern):
        raise exc.InvalidModelException(
            'Pattern or first_execution_time must be specified.'
        )
    if first_time:
        if (datetime.datetime.now() + datetime.timedelta(0, 60)) > first_time:
            raise exc.InvalidModelException(
                'first_execution_time must be at least 1 minute in the future.'
            )
        if not pattern and count and count > 1:
            raise exc.InvalidModelException(
                'Pattern must be provided if count is superior to 1.'
            )
    if pattern:
        try:
            croniter(pattern)
        except (ValueError, KeyError):
            raise exc.InvalidModelException(
                'The specified pattern is not valid: {}'.format(pattern)
            )


def create_cron_trigger(name, workflow_name, workflow_input,
                        workflow_params=None, pattern=None, first_time=None,
                        count=None, start_time=None, workflow_id=None):
    if not start_time:
        start_time = datetime.datetime.now()

    if isinstance(first_time, six.string_types):
        try:
            first_time = datetime.datetime.strptime(
                first_time,
                '%Y-%m-%d %H:%M'
            )
        except ValueError as e:
            raise exc.InvalidModelException(e.message)

    validate_cron_trigger_input(pattern, first_time, count)

    if first_time:
        next_time = first_time

        if not (pattern or count):
            count = 1
    else:
        next_time = get_next_execution_time(pattern, start_time)

    with db_api.transaction():
        wf_def = db_api.get_workflow_definition(
            workflow_id if workflow_id else workflow_name
        )

        eng_utils.validate_input(
            wf_def,
            workflow_input or {},
            parser.get_workflow_spec(wf_def.spec)
        )

        values = {
            'name': name,
            'pattern': pattern,
            'first_execution_time': first_time,
            'next_execution_time': next_time,
            'remaining_executions': count,
            'workflow_name': wf_def.name,
            'workflow_id': wf_def.id,
            'workflow_input': workflow_input or {},
            'workflow_params': workflow_params or {},
            'scope': 'private'
        }

        security.add_trust_id(values)

        trig = db_api.create_cron_trigger(values)

    return trig


def create_event_trigger(name, exchange, topic, event, workflow_id,
                         workflow_input=None, workflow_params=None):
    with db_api.transaction():
        wf_def = db_api.get_workflow_definition_by_id(workflow_id)

        eng_utils.validate_input(
            wf_def,
            workflow_input or {},
            parser.get_workflow_spec_by_definition_id(
                wf_def.id,
                wf_def.updated_at
            )
        )

        values = {
            'name': name,
            'workflow_id': workflow_id,
            'workflow_input': workflow_input or {},
            'workflow_params': workflow_params or {},
            'exchange': exchange,
            'topic': topic,
            'event': event,
        }

        security.add_trust_id(values)

        trig = db_api.create_event_trigger(values)

        trigs = db_api.get_event_triggers(insecure=True, exchange=exchange,
                                          topic=topic)
        events = [t.event for t in trigs]

        # NOTE(kong): Send RPC message within the db transaction, rollback if
        # any error occurs.
        rpc.get_event_engine_client().create_event_trigger(
            trig.to_dict(),
            events
        )

    return trig


def delete_event_trigger(event_trigger):
    with db_api.transaction():
        db_api.delete_event_trigger(event_trigger['id'])

        trigs = db_api.get_event_triggers(
            insecure=True,
            exchange=event_trigger['exchange'],
            topic=event_trigger['topic']
        )
        events = set([t.event for t in trigs])

        # NOTE(kong): Send RPC message within the db transaction, rollback if
        # any error occurs.
        rpc.get_event_engine_client().delete_event_trigger(
            event_trigger,
            list(events)
        )


def update_event_trigger(id, values):
    with db_api.transaction():
        trig = db_api.update_event_trigger(id, values)

        # NOTE(kong): Send RPC message within the db transaction, rollback if
        # any error occurs.
        rpc.get_event_engine_client().update_event_trigger(trig.to_dict())

    return trig
