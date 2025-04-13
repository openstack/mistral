# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from PlatformLibrary import PlatformLibrary

pl_lib = PlatformLibrary(managed_by_operator="true")

reduced_resources = dict(requests=dict(cpu='10m', memory='10Mi'), limits=dict(cpu='10m', memory='10Mi'))

def get_deployment_resources(name, namespace):
    deployment = pl_lib.get_deployment_entity(name, namespace)
    resources= deployment.spec.template.spec.containers[0].resources
    requests_cpu = resources.requests.get('cpu')
    requests_memory = resources.requests.get('memory')
    limits_cpu = resources.limits.get('cpu')
    limits_memory = resources.limits.get('memory')
    resources_dict = dict(requests=dict(cpu=requests_cpu, memory=requests_memory),
                          limits=dict(cpu=limits_cpu, memory=limits_memory))
    return resources_dict

def patch_deployment_resources(name, namespace, resources_dict=reduced_resources):
    deployment = pl_lib.get_deployment_entity(name, namespace)
    deployment.spec.template.spec.containers[0].resources = resources_dict
    pl_lib.patch_namespaced_deployment_entity(name, namespace, deployment)


