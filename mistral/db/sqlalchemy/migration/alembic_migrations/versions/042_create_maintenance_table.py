# Copyright 2023 OpenStack Foundation.
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

"""create maintenance table

Revision ID: 042
Revises: 041
Create Date: 2023-05-29 12:45:14.041458

"""

# revision identifiers, used by Alembic.
revision = '042'
down_revision = '041'

from alembic import op

from mistral.services import maintenance


def upgrade():
    connection = op.get_bind()

    connection.execute(
        """CREATE TABLE IF NOT EXISTS mistral_metrics
        (name VARCHAR(255) UNIQUE, value VARCHAR(255),
        id INT PRIMARY KEY DEFAULT 1)"""
    )

    connection.execute(
        """INSERT INTO mistral_metrics (id, name, value)
        VALUES (1, 'maintenance_status', %s)""",
        (maintenance.RUNNING,)
    )
