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

import os
import time

from PlatformLibrary import PlatformLibrary

environ = os.environ
managed_by_operator = environ.get("MISTRAL_MANAGED_BY_OPERATOR", "true")
namespace = environ.get("KUBERNETES_NAMESPACE")
service = environ.get("MISTRAL_HOST", "mistral")
timeout = 300
SERVICE_LABEL = "app"

if __name__ == '__main__':
    print("Checking Mistral deployments are ready")
    try:
        k8s_lib = PlatformLibrary(managed_by_operator)
    except Exception as e:
        print(e)
        exit(1)
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        try:
            deployments = k8s_lib.get_deployment_entities_count_for_service(namespace, service, SERVICE_LABEL)
            ready_deployments = k8s_lib.get_active_deployment_entities_count_for_service(namespace, service, SERVICE_LABEL)
            print(f'[Check status] deployments: {deployments}, ready deployments: {ready_deployments}')
        except Exception as e:
            print(e)
            continue
        if deployments == ready_deployments and deployments != 0:
            print("Mistral deployments are ready")
            exit(0)
        time.sleep(5)
    print(f'Mistral deployments are not ready at least {timeout} seconds')
    exit(1)
