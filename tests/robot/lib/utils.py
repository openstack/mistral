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

import time

from robot.api import logger


def timeout(func_timeout: int = 3 * 60):
    def decorator(func):
        func.last_exception = None

        def _wrapper(*args, **kwargs):
            timeout = time.time() + func_timeout
            while True:
                try:
                    if time.time() > timeout:
                        raise TimeoutError('Time is up')

                    return func(*args, **kwargs)
                except TimeoutError as e:
                    logger.error(func.last_exception)

                    raise e
                except BaseException as e:
                    logger.debug(e)
                    func.last_exception = e

                    time.sleep(10)

        return _wrapper

    return decorator
