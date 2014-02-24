# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

import yaml
from yaml import error
from mistral.workbook import workbook


def parse(workbook_definition):
    """Loads a workbook definition in YAML format as dictionary object."""
    try:
        return yaml.safe_load(workbook_definition)
    except error.YAMLError as exc:
        raise RuntimeError("Definition could not be parsed: %s\n" % exc)


def get_workbook(workbook_definition):
    return workbook.WorkbookSpec(parse(workbook_definition))
