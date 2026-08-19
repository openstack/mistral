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

from mistral.db.v2.sqlalchemy import models
from mistral.tests.unit import base

TOKEN = 'gAAAAA-super-secret-keystone-token'


class ModelReprMaskingTest(base.BaseTest):
    """The serialized security context must not leak via repr().

    ScheduledJob.auth_ctx and DelayedCall.auth_context hold a serialized
    MistralContext (auth token + service catalog). The ORM __repr__ used
    to dump every column, so formatting the object with %s leaked the
    token into the logs.
    """

    def test_scheduled_job_masks_auth_ctx(self):
        job = models.ScheduledJob()
        job.id = 'job-id'
        job.auth_ctx = {'auth_token': TOKEN, 'project_id': 'p1'}

        r = repr(job)

        self.assertNotIn(TOKEN, r)
        self.assertIn("'auth_ctx': '***'", r)
        # Non-sensitive columns stay visible.
        self.assertIn('job-id', r)

    def test_delayed_call_masks_auth_context(self):
        call = models.DelayedCall()
        call.id = 'call-id'
        call.auth_context = {'auth_token': TOKEN, 'project_id': 'p1'}

        r = repr(call)

        self.assertNotIn(TOKEN, r)
        self.assertIn("'auth_context': '***'", r)

    def test_to_dict_is_not_masked(self):
        # to_dict() is used for real serialization and must be untouched.
        job = models.ScheduledJob()
        job.auth_ctx = {'auth_token': TOKEN}

        self.assertEqual(TOKEN, job.to_dict()['auth_ctx']['auth_token'])
