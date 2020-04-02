# Copyright 2020 - Nokia Software.
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


import json
import math
import random
import string

from rally.task import validation
from rally_openstack import consts
from rally_openstack import scenario
from rally_openstack.scenarios.mistral import utils


def random_string(length=10):
    """Generate a random string of given length """

    letters = string.ascii_lowercase

    return ''.join(random.choices(letters, k=length))


class MistralExpressionScenario(utils.MistralScenario):

    def run(self, tasks_number=50, params_size_mb=5):
        wf_text, wf_name = self.create_wf_string(tasks_number)
        params = self.create_params(params_size_mb)

        self._create_workflow(wf_text)
        self._create_execution(wf_name, **params)

    def create_params(self, size_mb):
        block_size_mb = 0.2
        rand_string = random_string(105400)
        number_of_fields = math.floor(size_mb / block_size_mb)
        data_list = ''
        #  each one of these blocks is 200kb
        data_template = """
                "data%s":
                {
                  "dummy": 5470438,
                  "data_value": -796997888,
                  "sub_data":
                  {
                    "meta_data":
                    {
                      "value": "%s",
                      "text": "dummy text"
                    },
                    "field1": "%s",
                    "field2": false,
                    "field3":
                    {
                      "value1": -1081872761.2081857,
                      "value2": -1081872761.2081857
                    }
                  }
                },
"""
        wf_params = """
        {
          "field": "some Value",
            "data":
              {
                {{{__DATA_LIST__}}}
              }
        }
"""
        for i in range(1, int(number_of_fields + 1)):
            data_list += data_template % (i, rand_string, rand_string)

        data_list = data_list[:-2]

        wf_params = wf_params.replace('{{{__DATA_LIST__}}}', data_list)
        params = json.loads(wf_params)

        return params

    def get_query(self):
        raise NotImplementedError

    def create_wf_string(self, tasks_number):
        wf_tasks = ''
        wf_name = 'wf_{}'.format(random_string(5))

        query = self.get_query()

        wf_text = """
            version: '2.0'
            {}:
              tasks:
                task0:
                  action: std.noop
                {{{__TASK_LIST__}}}
            """
        task_template = """
                task{}:
                  action: std.noop
                  publish:
                     output{}: {}
            """

        for i in range(1, tasks_number + 1):
            wf_tasks += task_template.format(i, i, query)

        wf_text = wf_text.replace('{{{__TASK_LIST__}}}', wf_tasks)

        wf_text = wf_text.format(wf_name)

        return wf_text, wf_name


@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_services", services=[consts.Service.MISTRAL])
@scenario.configure(name="MistralExecutions.YaqlExpression",
                    platform="openstack")
class YaqlExpressionScenario(MistralExpressionScenario):

    def get_query(self):
        return '<% data %>'


@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_services", services=[consts.Service.MISTRAL])
@scenario.configure(name="MistralExecutions.JinjaExpression",
                    platform="openstack")
class JinjaExpressionScenario(MistralExpressionScenario):

    def get_query(self):
        return '{{ data }} '
