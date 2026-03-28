# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
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

import threading


class TimeoutThreadWithException(threading.Thread):
    """Thread raising exception after timeout"""

    def __init__(self, timeout):
        super().__init__()
        self.timeout = timeout
        self.timer = threading.Timer(timeout, self._timeout)
        self.exception = None

    def stop(self):
        self.timer.cancel()

    def run(self):
        # This method is called when the thread actually starts (.start())
        self.timer.start()

    def _timeout(self):
        # We can't raise from a thread, instead, we prepare
        # an exception so that the main process can read that and decide to
        # re-raise or not
        self.exception = Exception(
            "Timeout after %(secs)s seconds" %
            {'secs': self.timeout}
        )
