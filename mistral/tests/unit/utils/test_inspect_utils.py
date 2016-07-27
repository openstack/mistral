# Copyright 2014 - Mirantis, Inc.
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

import time

from mistral.actions import std_actions
from mistral.tests.unit import base
from mistral.utils import inspect_utils as i_u
from mistral.workflow import commands


class InspectUtilsTest(base.BaseTest):
    def test_get_parameters_str(self):
        action_class = std_actions.HTTPAction
        parameters_str = i_u.get_arg_list_as_str(action_class.__init__)

        http_action_params = (
            'url, method="GET", params=null, body=null, '
            'headers=null, cookies=null, auth=null, '
            'timeout=null, allow_redirects=null, '
            'proxies=null, verify=null'
        )

        self.assertEqual(http_action_params, parameters_str)

    def test_get_parameters_str_all_mandatory(self):
        clazz = commands.RunTask
        parameters_str = i_u.get_arg_list_as_str(clazz.__init__)

        self.assertEqual('wf_ex, wf_spec, task_spec, ctx', parameters_str)

    def test_get_parameters_str_with_function_parameter(self):

        def test_func(foo, bar=None, test_func=time.sleep):
            pass

        parameters_str = i_u.get_arg_list_as_str(test_func)

        self.assertEqual("foo, bar=null", parameters_str)
