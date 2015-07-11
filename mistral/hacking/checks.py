# Copyright (c) 2014 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import re


oslo_namespace_imports_dot = re.compile(r"import[\s]+oslo[.][^\s]+")
oslo_namespace_imports_from_dot = re.compile(r"from[\s]+oslo[.]")
oslo_namespace_imports_from_root = re.compile(r"from[\s]+oslo[\s]+import[\s]+")


def check_oslo_namespace_imports(logical_line):
    if re.match(oslo_namespace_imports_from_dot, logical_line):
        msg = ("O323: '%s' must be used instead of '%s'.") % (
            logical_line.replace('oslo.', 'oslo_'),
            logical_line)
        yield(0, msg)
    elif re.match(oslo_namespace_imports_from_root, logical_line):
        msg = ("O323: '%s' must be used instead of '%s'.") % (
            logical_line.replace('from oslo import ', 'import oslo_'),
            logical_line)
        yield(0, msg)
    elif re.match(oslo_namespace_imports_dot, logical_line):
        msg = ("O323: '%s' must be used instead of '%s'.") % (
            logical_line.replace('import', 'from').replace('.', ' import '),
            logical_line)
        yield(0, msg)


def factory(register):
    register(check_oslo_namespace_imports)
