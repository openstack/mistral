# Copyright 2020 Nokia Software.
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

"""namespace support for workbooks table postgresql

Revision ID: 036
Revises: 035
Create Date: 2020-1-6 9:49:20

"""

# revision identifiers, used by Alembic.

from alembic import op
from sqlalchemy.engine import reflection

revision = '036'
down_revision = '035'


def upgrade():

    inspect = reflection.Inspector.from_engine(op.get_bind())

    unique_constraints = [
        unique_constraint['name'] for unique_constraint in
        inspect.get_unique_constraints('workbooks_v2')
    ]

    if 'workbooks_v2_name_project_id_key' in unique_constraints:
        op.drop_constraint('workbooks_v2_name_project_id_key',
                           table_name='workbooks_v2')
