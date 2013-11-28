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
import uuid

from mistral.db.sqlalchemy import model_base as mb

## Helpers


def _generate_unicode_uuid():
    return unicode(str(uuid.uuid4()))


def _id_column():
    return sa.Column(sa.String(36),
                     primary_key=True,
                     default=_generate_unicode_uuid)


class Event(mb.MistralBase):
    """Contains all info about event."""

    __tablename__ = 'events'

    __table_args__ = (
        sa.UniqueConstraint('name'),
    )

    id = _id_column()
    name = sa.Column(sa.String(80), nullable=False)
