#  Copyright 2019 - Nokia Corporation
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from unittest import TestCase

from mistral.utils import safe_yaml


class TestSafeLoader(TestCase):
    def test_safe_load(self):
        yaml_text = """
        version: '2.0'

        wf1:
          type: direct

          input:
            - a: &a ["lol","lol","lol","lol","lol"]
            - b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]
            - c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b]
            - d: &d [*c,*c,*c,*c,*c,*c,*c,*c,*c]
            - e: &e [*d,*d,*d,*d,*d,*d,*d,*d,*d]
            - f: &f [*e,*e,*e,*e,*e,*e,*e,*e,*e]
            - g: &g [*f,*f,*f,*f,*f,*f,*f,*f,*f]
            - h: &h [*g,*g,*g,*g,*g,*g,*g,*g,*g]
            - i: &i [*h,*h,*h,*h,*h,*h,*h,*h,*h]


          tasks:
            hello:
              action: std.echo output="Hello"
              wait-before: 1
              publish:
                result: <% task(hello).result %>
        """

        result = {
            'version': '2.0',
            'wf1':
                {'type': 'direct',
                 'input': [
                     {'a': '&a ["lol","lol","lol","lol","lol"]'},
                     {'b': '&b [*a,*a,*a,*a,*a,*a,*a,*a,*a]'},
                     {'c': '&c [*b,*b,*b,*b,*b,*b,*b,*b,*b]'},
                     {'d': '&d [*c,*c,*c,*c,*c,*c,*c,*c,*c]'},
                     {'e': '&e [*d,*d,*d,*d,*d,*d,*d,*d,*d]'},
                     {'f': '&f [*e,*e,*e,*e,*e,*e,*e,*e,*e]'},
                     {'g': '&g [*f,*f,*f,*f,*f,*f,*f,*f,*f]'},
                     {'h': '&h [*g,*g,*g,*g,*g,*g,*g,*g,*g]'},
                     {'i': '&i [*h,*h,*h,*h,*h,*h,*h,*h,*h]'}],
                 'tasks':
                    {'hello': {
                        'action': 'std.echo output="Hello"',
                        'wait-before': 1, 'publish':
                            {'result': '<% task(hello).result %>'}
                    }}
                 }
        }
        self.assertEqual(result, safe_yaml.load(yaml_text))
