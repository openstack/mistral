#  Copyright 2023 - NetCracker Technology Corp.
# Modified in 2025 by NetCracker Technology Corp.
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import os

from alembic import config as alembic_cfg
from mistral.config import CONF
from mistral.monitoring import monitoring_server
from oslo_log import log as logging
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

LOG = logging.getLogger(__name__)


def main():
    config = alembic_cfg.Config(
        os.path.join(os.path.dirname(__file__), 'alembic.ini')
    )
    config.set_main_option(
        'script_location',
        'mistral.db.sqlalchemy.migration:alembic_migrations'
    )
    # attach the Mistral conf to the Alembic conf
    config.mistral_config = CONF
    logging.register_options(CONF)
    CONF(project='mistral')
    logging.setup(CONF, 'Mistral')

    monitoring = monitoring_server.MonitoringServer()
    monitoring.start()


if __name__ == '__main__':
    main()
