# Copyright 2014 - Mirantis, Inc.
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

from oslo_config import cfg
from oslo_log import log as logging

from mistral import config
from mistral.db.v2 import api as db_api
from mistral.services import action_manager
from mistral.services import workflows


CONF = cfg.CONF


def main():
    config.parse_args()

    if len(CONF.config_file) == 0:
        print("Usage: sync_db --config-file <path-to-config-file>")
        return exit(1)

    logging.setup(CONF, 'Mistral')

    db_api.setup_db()

    action_manager.sync_db()
    workflows.sync_db()


if __name__ == '__main__':
    main()
