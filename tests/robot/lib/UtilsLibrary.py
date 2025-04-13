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

import uuid

from robot.api import logger
from robot.errors import PassExecution
from robot.utils import asserts


class UtilsLibrary(object):
    def _is_true(self, condition):
        return bool(condition)

    def skip_execution_if(self, condition):
        if self._is_true(condition):
            logger.info('Execution skipped')
            raise PassExecution('Execution skipped')
    
    def skip_if_auth_is_disalbed(self, auth):
        if auth != 'True':
            logger.info('Execution skipped')
            raise PassExecution('Execution skipped')

        logger.debug(f'Auth var is ${auth}')

    def generate_uuid(self):
        return str(uuid.uuid4())

    def dictionary_should_contain(self, dict, key, value):
        logger.debug(f"Dict: {dict}, key: {key}, value: {value}")

        asserts.assert_true(dict[key] == value)

    def ret_long_dict(self):
        return {
            "a": {
                "b": {
                    "c1": {
                        "c1": 1
                    },
                    "c2": {
                        "c2": 2
                    }
                }
            }
        }
