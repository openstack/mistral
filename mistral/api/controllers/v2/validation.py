# Copyright 2015 - StackStorm, Inc.
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


import pecan
from pecan import rest

from mistral import exceptions as exc


class SpecValidationController(rest.RestController):

    def __init__(self, parser):
        super(SpecValidationController, self).__init__()

        self._parse_func = parser

    @pecan.expose('json')
    def post(self):
        """Validate a spec."""
        definition = pecan.request.text

        try:
            self._parse_func(definition)
        except exc.DSLParsingException as e:
            return {'valid': False, 'error': e.message}

        return {'valid': True}
