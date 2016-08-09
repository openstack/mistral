# Copyright 2015 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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
from oslo_utils import timeutils

from mistral.db.v2.sqlalchemy import api as db_api
from mistral.db.v2.sqlalchemy import models as db_models
from mistral.tests.unit import base as test_base


DELAYED_CALL = {
    'factory_method_path': 'my_factory_method',
    'target_method_name': 'my_target_method',
    'method_arguments': None,
    'serializers': None,
    'auth_context': None,
    'execution_time': timeutils.utcnow()
}


class InsertOrIgnoreTest(test_base.DbTestCase):
    def setUp(self):
        super(InsertOrIgnoreTest, self).setUp()

        cfg.CONF.set_default('auth_enable', True, group='pecan')

        self.addCleanup(
            cfg.CONF.set_default,
            'auth_enable',
            False,
            group='pecan'
        )

    def test_insert_or_ignore_without_conflicts(self):
        db_api.insert_or_ignore(
            db_models.DelayedCall,
            DELAYED_CALL.copy()
        )

        delayed_calls = db_api.get_delayed_calls()

        self.assertEqual(1, len(delayed_calls))

        delayed_call = delayed_calls[0]

        self._assert_dict_contains_subset(DELAYED_CALL, delayed_call.to_dict())

    def test_insert_or_ignore_with_conflicts(self):
        # Insert the first object.
        values = DELAYED_CALL.copy()

        values['unique_key'] = 'key'

        db_api.insert_or_ignore(db_models.DelayedCall, values)

        delayed_calls = db_api.get_delayed_calls()

        self.assertEqual(1, len(delayed_calls))

        delayed_call = delayed_calls[0]

        self._assert_dict_contains_subset(DELAYED_CALL, delayed_call.to_dict())

        # Insert the second object with the same unique key.
        # We must not get exceptions and new object must not be saved.
        values = DELAYED_CALL.copy()

        values['unique_key'] = 'key'

        db_api.insert_or_ignore(db_models.DelayedCall, values)

        delayed_calls = db_api.get_delayed_calls()

        self.assertEqual(1, len(delayed_calls))

        delayed_call = delayed_calls[0]

        self._assert_dict_contains_subset(DELAYED_CALL, delayed_call.to_dict())
