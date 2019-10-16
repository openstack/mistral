#    Copyright 2019 OpenStack Foundation.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg


from mistral import exceptions as exc
from mistral.services import workflows as wf_service
from mistral.tests.unit.engine import base
from testtools import ExpectedException


# Use the set_default method to set value otherwise in certain test cases
# the change in value is not permanent.
cfg.CONF.set_default('auth_enable', False, group='pecan')


class NameValidationTest(base.EngineTestCase):
    @staticmethod
    def test_workflow_name_validation():
        wf = """
        version: 2.0
        wf name with space:
          tasks:
            t1:
              action: a1
        """
        with ExpectedException(exc.InvalidModelException,
                               "Name 'wf name with space' "
                               "must not contain spaces"):
            wf_service.create_workflows(wf)
