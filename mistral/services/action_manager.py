# Copyright 2014 - Mirantis, Inc.
# Copyright 2014 - StackStorm, Inc.
# Copyright 2020 Nokia Software.
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

from oslo_log import log as logging

from mistral.db.v2 import api as db_api
from mistral.services import adhoc_actions
from mistral_lib import utils


# TODO(rakhmerov): This module won't be needed after we add action providers

LOG = logging.getLogger(__name__)

ACTIONS_PATH = 'resources/actions'


def _register_preinstalled_adhoc_actions():
    action_paths = utils.get_file_list(ACTIONS_PATH)

    for action_path in action_paths:
        action_definition = open(action_path).read()

        adhoc_actions.create_or_update_actions(
            action_definition,
            scope='public'
        )


def sync_db():
    with db_api.transaction():
        _register_preinstalled_adhoc_actions()
