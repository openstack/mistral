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

def parameters_are_enabled(environ, *variable_names) -> bool:
    for variable in variable_names:
        if not environ.get(variable):
            return False
        value = environ.get(variable)
        if type(value) is str and value.lower() == 'false':
            return False
    return True

def get_excluded_tags(environ) -> list:
    excluded_tags = ["custom-actions"]
    if not parameters_are_enabled(environ, "RUN_BENCHMARKS"):
        excluded_tags.append("mistral_svt")
        if not parameters_are_enabled(environ, "AUTH_ENABLE"):
            excluded_tags.append("security")
    else:
        excluded_tags.extend(["basic", "security", "dr", "heartbeat", "benchmark_skip"])
    if not parameters_are_enabled(environ, "PROMETHEUS_URL"):
        excluded_tags.append("alerts")
    return excluded_tags