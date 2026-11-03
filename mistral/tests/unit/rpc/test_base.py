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

from mistral import exceptions as exc
from mistral.rpc import base as rpc_base
from mistral.tests.unit import base


class NoArgsError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class WrapMessagingExceptionTest(base.BaseTest):
    def _call_raising(self, error):
        @rpc_base.wrap_messaging_exception
        def method():
            raise error

        return self.assertRaises(exc.MistralException, method)

    def test_exception_with_args(self):
        e = self._call_raising(ValueError('Bad value', 'extra'))

        self.assertEqual('ValueError: Bad value', str(e))

    def test_exception_without_args(self):
        e = self._call_raising(
            NoArgsError(message='Volume could not be found.')
        )

        self.assertEqual('NoArgsError: Volume could not be found.', str(e))
