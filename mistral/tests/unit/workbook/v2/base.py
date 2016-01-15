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

import copy

import yaml

from mistral import exceptions as exc
from mistral.tests.unit import base
from mistral import utils
from mistral.workbook import parser as spec_parser


class WorkflowSpecValidationTestCase(base.BaseTest):

    def __init__(self, *args, **kwargs):
        super(WorkflowSpecValidationTestCase, self).__init__(*args, **kwargs)

        # The relative resource path is ./mistral/tests/resources/workbook/v2.
        self._resource_path = 'workbook/v2'

        self._spec_parser = spec_parser.get_workflow_list_spec_from_yaml

        self._dsl_blank = {
            'version': '2.0',
            'test': {
                'type': 'direct'
            }
        }

        self._dsl_tasks = {
            'get': {
                'action': 'std.http',
                'input': {
                    'url': 'http://www.openstack.org'
                }
            },
            'echo': {
                'action': 'std.echo',
                'input': {
                    'output': 'This is a test.'
                }
            },
            'email': {
                'action': 'std.email',
                'input': {
                    'from_addr': 'mistral@example.com',
                    'to_addrs': ['admin@example.com'],
                    'subject': 'Test',
                    'body': 'This is a test.',
                    'smtp_server': 'localhost',
                    'smtp_password': 'password'
                }
            }
        }

    def _parse_dsl_spec(self, dsl_file=None, add_tasks=False,
                        changes=None, expect_error=False):
        if dsl_file and add_tasks:
            raise Exception('The add_tasks option is not a valid '
                            'combination with the dsl_file option.')

        if dsl_file:
            dsl_yaml = base.get_resource(self._resource_path + '/' + dsl_file)

            if changes:
                dsl_dict = yaml.safe_load(dsl_yaml)
                utils.merge_dicts(dsl_dict, changes)
                dsl_yaml = yaml.safe_dump(dsl_dict, default_flow_style=False)
        else:
            dsl_dict = copy.deepcopy(self._dsl_blank)

            if add_tasks:
                dsl_dict['test']['tasks'] = copy.deepcopy(self._dsl_tasks)

            if changes:
                utils.merge_dicts(dsl_dict, changes)

            dsl_yaml = yaml.safe_dump(dsl_dict, default_flow_style=False)

        if not expect_error:
            return self._spec_parser(dsl_yaml)
        else:
            return self.assertRaises(
                exc.DSLParsingException,
                self._spec_parser,
                dsl_yaml
            )


class WorkbookSpecValidationTestCase(WorkflowSpecValidationTestCase):

    def __init__(self, *args, **kwargs):
        super(WorkbookSpecValidationTestCase, self).__init__(*args, **kwargs)

        self._spec_parser = spec_parser.get_workbook_spec_from_yaml

        self._dsl_blank = {
            'version': '2.0',
            'name': 'test_wb'
        }

    def _parse_dsl_spec(self, dsl_file=None,
                        changes=None, expect_error=False):
        return super(WorkbookSpecValidationTestCase, self)._parse_dsl_spec(
            dsl_file=dsl_file, add_tasks=False, changes=changes,
            expect_error=expect_error)
