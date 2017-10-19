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

from mistral.tests.unit import base
from mistral.utils import expression_utils as e_u


JSON_INPUT = [
    {
        "this": "is valid",
    },
    {
        "so": "is this",
        "and": "this too",
        "might": "as well",
    },
    "validaswell"
]


JSON_TO_YAML_STR = """- this: is valid
- and: this too
  might: as well
  so: is this
- validaswell
"""


class ExpressionUtilsTest(base.BaseTest):
    def test_yaml_dump(self):
        yaml_str = e_u.yaml_dump_(None, JSON_INPUT)

        self.assertEqual(JSON_TO_YAML_STR, yaml_str)
