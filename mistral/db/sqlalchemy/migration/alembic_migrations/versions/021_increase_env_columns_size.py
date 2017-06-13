# Copyright 2015 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Increase environments_v2 column size from JsonDictType to JsonLongDictType

Revision ID: 021
Revises: 020
Create Date: 2017-06-13 13:29:41.636094

"""

# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'

from alembic import op
from mistral.db.sqlalchemy import types as st


def upgrade():
    # Changing column types from JsonDictType to JsonLongDictType
    op.alter_column('environments_v2', 'variables',
                    type_=st.JsonLongDictType())
