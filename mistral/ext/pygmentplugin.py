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

import re

from pygments import lexer
from pygments import token


class MistralLexer(lexer.RegexLexer):

    name = 'Mistral'
    aliases = ['mistral']

    flags = re.MULTILINE | re.UNICODE

    tokens = {
        "root": [
            (r'^(\s)*(workflows|tasks|input|output|type)(\s)*:',
                token.Keyword),
            (r'^(\s)*(version|name|description)(\s)*:', token.Keyword),
            (r'^(\s)*(publish|timeout|retry|with\-items)(\s)*:',
                token.Keyword),
            (r'^(\s)*(on\-success|on\-error|on\-complete)(\s)*:',
                token.Keyword),
            (r'^(\s)*(action|workflow)(\s)*:', token.Keyword, 'call'),
            (r'(\-|\:)(\s)*(fail|succeed|pause)(\s)+', token.Operator.Word),
            (r'<%', token.Name.Entity, 'expression'),
            (r'\{\{', token.Name.Entity, 'expression'),
            (r'#.*$', token.Comment),
            (r'(^|\s|\-)+\d+', token.Number),
            lexer.include("generic"),
        ],
        "expression": [
            (r'\$', token.Operator),
            (r'\s(json_pp|task|tasks|execution|env|uuid)(?!\w)',
                token.Name.Builtin),
            lexer.include("generic"),
            (r'%>', token.Name.Entity, '#pop'),
            (r'}\\}', token.Name.Entity, '#pop'),
        ],
        "call": [
            (r'(\s)*[\w\.]+($|\s)', token.Name.Function),
            lexer.default('#pop'),
        ],
        "generic": [
            (r'%>', token.Name.Entity, '#pop'),
            (r'}\\}', token.Name.Entity, '#pop'),
            (r'(\-|:|=|!|\[|\]|<|>|\/|\*)', token.Operator),
            (r'(null|None|True|False)', token.Name.Builtin),
            (r'"(\\\\|\\"|[^"])*"', token.String.Double),
            (r"'(\\\\|\\'|[^'])*'", token.String.Single),
            (r'\W|\w|\s|\(|\)|,|\.', token.Text),
        ]
    }
