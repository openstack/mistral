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

from mistral.expressions import std_functions
from mistral.tests.unit import base


class YamlParseHardeningTest(base.BaseTest):
    """yaml_parse must not resolve/expand YAML anchors and aliases.

    Raw yaml.safe_load supports anchors/aliases and is vulnerable to the
    "billion laughs" entity-expansion DoS. yaml_parse is reachable from
    any workflow expression with attacker-controlled input, so it must
    use the hardened loader that treats anchors/aliases as plain text.
    """

    def test_aliases_are_not_resolved(self):
        doc = "a: &x foo\nb: *x\n"

        result = std_functions.yaml_parse_(None, doc)

        # With a hardened loader the alias is a plain string, not the
        # value of the anchor.
        self.assertEqual('*x', result['b'])
        self.assertNotEqual('foo', result['b'])

    def test_billion_laughs_does_not_expand(self):
        bomb = (
            "a: &a [x,x,x,x,x,x,x,x,x]\n"
            "b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]\n"
            "c: [*b,*b,*b,*b,*b,*b,*b,*b,*b]\n"
        )

        result = std_functions.yaml_parse_(None, bomb)

        # The aliases are not expanded into nested lists.
        self.assertFalse(isinstance(result['c'][0], list))
