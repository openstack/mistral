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

import sqlalchemy as sa

from mistral.db.sqlalchemy import models as m
from mistral.openstack.common.db.sqlalchemy import session as db_session
from mistral.openstack.common import log as logging
from mistral.openstack.common.db import exception as db_exc


LOG = logging.getLogger(__name__)

get_engine = db_session.get_engine
get_session = db_session.get_session


def to_dict(func):
    def decorator(*args, **kwargs):
        res = func(*args, **kwargs)

        if isinstance(res, list):
            return [item.to_dict() for item in res]

        if res:
            return res.to_dict()
        else:
            return None

    return decorator


def model_query(model, session=None):
    """Query helper.

    :param model: base model to query
    :param context: context to query under
    :param project_only: if present and context is user-type, then restrict
            query to match the context's tenant_id.
    """
    session = session or get_session()

    return session.query(model)


def setup_db():
    try:
        engine = db_session.get_engine(sqlite_fk=True)
        m.Event.metadata.create_all(engine)
    except sa.exc.OperationalError as e:
        LOG.exception("Database registration exception: %s", e)
        return False
    return True


def drop_db():
    try:
        engine = db_session.get_engine(sqlite_fk=True)
        m.Event.metadata.drop_all(engine)
    except Exception as e:
        LOG.exception("Database shutdown exception: %s", e)
        return False
    return True


def event_create(values):
    values = values.copy()
    event = m.Event()
    event.update(values)

    session = get_session()
    with session.begin():
        try:
            event.save(session=session)
        except db_exc.DBDuplicateEntry as e:
            LOG.exception("Database registration exception: %s", e)
            ##TODO(akuznetsov) create special exception for this case
            raise Exception

    return event_get(event.id)


def event_update(event_id, values):
    values = values.copy()

    session = get_session()
    with session.begin():
        event = _event_get(event_id, session)
        if event is None:
            ##TODO(akuznetsov) create special exception for this case
            raise Exception
        event.update(values)

    return event


@to_dict
def get_next_events(time):
    query = model_query(m.Event, get_session())
    query = query.filter(m.Event.next_execution_time < time)
    query = query.order_by(m.Event.next_execution_time)
    return query.all()


def _event_get(event_id, session):
    query = model_query(m.Event, session)
    return query.filter_by(id=event_id).first()


@to_dict
def event_get(event_id):
    return _event_get(event_id, get_session())
