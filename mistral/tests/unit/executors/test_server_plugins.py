# Copyright 2017 - Brocade Communications Systems, Inc.
# Copyright 2018 - Extreme Networks, Inc.
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
from stevedore import exception as sd_exc

from mistral.executors import base as exe
from mistral.executors import default_executor as d
from mistral.executors import remote_executor as r
from mistral.tests.unit.executors import base


LOG = logging.getLogger(__name__)


class PluginTestCase(base.ExecutorTestCase):

    def tearDown(self):
        exe.cleanup()
        super(PluginTestCase, self).tearDown()

    def test_get_local_executor(self):
        executor = exe.get_executor('local')

        self.assertIsInstance(executor, d.DefaultExecutor)

    def test_get_remote_executor(self):
        executor = exe.get_executor('remote')

        self.assertIsInstance(executor, r.RemoteExecutor)

    def test_get_bad_executor(self):
        self.assertRaises(sd_exc.NoMatches, exe.get_executor, 'foobar')
