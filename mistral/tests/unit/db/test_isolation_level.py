# Copyright 2026 - OVHcloud.
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

from unittest import mock

from mistral.db.sqlalchemy import base as db_base
from mistral.tests.unit import base


class IsolationLevelTest(base.BaseTest):
    """Checks that READ COMMITTED is set when the engine gets created.

    The named lock synchronization pattern (used e.g. to deduplicate
    the creation of "join" tasks across several engines) requires the
    READ COMMITTED transaction isolation level. It must be applied on
    the engine no matter which code path triggers its creation.
    """

    def _create_facade(self, backend_name):
        engine = mock.MagicMock()
        engine.url.get_backend_name.return_value = backend_name

        ctx = mock.MagicMock()
        ctx.writer.get_engine.return_value = engine

        with mock.patch.object(db_base, '_facade', None):
            with mock.patch.object(
                db_base.enginefacade,
                'transaction_context',
                return_value=ctx
            ):
                db_base._get_facade()

        return engine

    def test_mysql_gets_read_committed(self):
        engine = self._create_facade('mysql')

        engine.update_execution_options.assert_called_once_with(
            isolation_level='READ COMMITTED'
        )

    def test_sqlite_keeps_default_isolation(self):
        engine = self._create_facade('sqlite')

        engine.update_execution_options.assert_not_called()
