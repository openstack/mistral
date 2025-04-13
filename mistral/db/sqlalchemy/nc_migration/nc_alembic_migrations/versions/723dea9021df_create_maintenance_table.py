# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""create maintenance table

Revision ID: 723dea9021df
Revises: d563bed642f6
Create Date: 2018-06-27 07:05:17.837054

"""

# revision identifiers, used by Alembic.
revision = '723dea9021df'
down_revision = None

from alembic import op
from mistral.services import maintenance


def upgrade():
    # TODO(vgvoleg): Need to use SA Table instead raw query.
    # Now it's impossible because the multitenancy.
    connection = op.get_bind()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS mistral_maintenance
        (status TEXT, id INT PRIMARY KEY DEFAULT 1)
    """)

    connection.execute("""INSERT into mistral_maintenance (id, status)
    VALUES (1, %s)
    ON CONFLICT (id) DO UPDATE
    SET status = EXCLUDED.status""", (maintenance.RUNNING,))
