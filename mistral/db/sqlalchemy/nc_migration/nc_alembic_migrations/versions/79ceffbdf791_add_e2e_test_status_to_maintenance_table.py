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

"""Add e2e test status to maintenance table

Revision ID: 79ceffbdf791
Revises: 723dea9021df
Create Date: 2019-07-03 08:31:02.833643

"""

# revision identifiers, used by Alembic.
revision = '79ceffbdf791'
down_revision = '723dea9021df'

from alembic import op


def upgrade():
    connection = op.get_bind()

    connection.execute("""INSERT into mistral_maintenance (id, status)
        VALUES (2, %s)
        ON CONFLICT (id) DO UPDATE
        SET status = EXCLUDED.status""", ("0",))
