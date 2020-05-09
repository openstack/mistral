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
from pathlib import Path

from rally.common import cfg
from rally.task import validation
from rally_openstack import consts
from rally_openstack import scenario
from rally_openstack.scenarios.mistral import utils

CONF = cfg.CONF

SCENARIO_TIMEOUT_SEC = 16000

home_dir = str(Path.home())
wf_dir = '%s/.rally/extra/scenarios/big_wf/' % home_dir

action_files = ['dummy_actions.yaml', 'dummy_actions_nuage.yaml']
common_workflow_files = ['sub_wfs.yaml']


class MistralHugeWorkflowScenario(utils.MistralScenario):
    main_wf_file_name = ''
    params_filename = ''
    wf_name = ''
    created_wfs = []
    created_wbs = []

    def run(self):
        namespace = ''
        CONF.openstack.mistral_execution_timeout = SCENARIO_TIMEOUT_SEC

        self.create_common_workflows()
        self.create_actions()
        self.create_main_workflow(namespace=namespace)
        params = self._read_params_from_file()

        self.run_workflow(params, namespace=namespace)
        self.clean_after_scenario(namespace=namespace)

    def clean_after_scenario(self, namespace=''):
        for wf in self.created_wfs:
            self._delete_workflow(wf, namespace=namespace)

        for wb in self.created_wbs:
            self._delete_workbook(wb, namespace=namespace)

    def create_common_workflows(self):
        for file in common_workflow_files:
            with open(wf_dir + file, 'r+') as f:
                definition = f.read()
                wfs = self._create_workflow(definition)

                for wf in wfs:
                    self.created_wfs.append(wf.name)

    def create_actions(self):
        for file in action_files:
            with open(wf_dir + file, 'r+') as f:
                definition = f.read()
                wb = self._create_workbook(definition)

                self.created_wbs.append(wb.name)

    def _create_workbook(self, definition, namespace=''):
        return self.clients("mistral").workbooks.create(
            definition,
            namespace=namespace
        )

    def _read_params_from_file(self):
        with open(wf_dir + self.params_filename, 'r+') as f:
            params_string = f.read()
            params = json.loads(params_string)

            return params

    def run_workflow(self, params, namespace=''):
        input = {}

        self._create_execution(
            self.wf_name,
            wf_input=input,
            namespace=namespace,
            **params
        )

    def create_main_workflow(self, namespace=''):
        with open(wf_dir + self.main_wf_file_name, 'r+') as f:
            definition = f.read()
            wfs = self._create_workflow(definition, namespace=namespace)

            for wf in wfs:
                self.created_wfs.append(wf.name)


@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_services", services=[consts.Service.MISTRAL])
@scenario.configure(name="MistralExecutions.TerminateScenario",
                    platform="openstack")
class TerminateScenario(MistralHugeWorkflowScenario):
    main_wf_file_name = 'terminate_wf.yaml'
    params_filename = 'terminate_params.json'
    wf_name = 'mistral_cmg_terminate'


@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_services", services=[consts.Service.MISTRAL])
@scenario.configure(name="MistralExecutions.DeployScenario",
                    platform="openstack")
class DeployScenario(MistralHugeWorkflowScenario):
    main_wf_file_name = 'deploy_wf.yaml'
    params_filename = 'deploy_params.json'
    wf_name = 'mistral_cmg_deploy'
