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

"""Mistral's pep8 extensions.

In order to make the review process faster and easier for core devs we are
adding some Mistral specific pep8 checks. This will catch common errors.

There are two types of pep8 extensions. One is a function that takes either
a physical or logical line. The physical or logical line is the first param
in the function definition and can be followed by other parameters supported
by pep8. The second type is a class that parses AST trees. For more info
please see pep8.py.
"""

import ast
import re
import six


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


class BaseASTChecker(ast.NodeVisitor):
    """Provides a simple framework for writing AST-based checks.

    Subclasses should implement visit_* methods like any other AST visitor
    implementation. When they detect an error for a particular node the
    method should call ``self.add_error(offending_node)``. Details about
    where in the code the error occurred will be pulled from the node
    object.

    Subclasses should also provide a class variable named CHECK_DESC to
    be used for the human readable error message.

    """

    def __init__(self, tree, filename):
        """This object is created automatically by pep8.

        :param tree: an AST tree
        :param filename: name of the file being analyzed
                         (ignored by our checks)
        """
        self._tree = tree
        self._errors = []

    def run(self):
        """Called automatically by pep8."""
        self.visit(self._tree)

        return self._errors

    def add_error(self, node, message=None):
        """Add an error caused by a node to the list of errors for pep8."""
        message = message or self.CHECK_DESC
        error = (node.lineno, node.col_offset, message, self.__class__)

        self._errors.append(error)


class CheckForLoggingIssues(BaseASTChecker):
    CHECK_DESC = ('M001 Using the deprecated Logger.warn')
    LOG_MODULES = ('logging', 'oslo_log.log')

    def __init__(self, tree, filename):
        super(CheckForLoggingIssues, self).__init__(tree, filename)

        self.logger_names = []
        self.logger_module_names = []

        # NOTE(dstanek): This kinda accounts for scopes when talking
        # about only leaf node in the graph.
        self.assignments = {}

    def _filter_imports(self, module_name, alias):
        """Keeps lists of logging imports."""
        if module_name in self.LOG_MODULES:
            self.logger_module_names.append(alias.asname or alias.name)

    def visit_Import(self, node):
        for alias in node.names:
            self._filter_imports(alias.name, alias)

        return super(CheckForLoggingIssues, self).generic_visit(node)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            full_name = '%s.%s' % (node.module, alias.name)
            self._filter_imports(full_name, alias)

        return super(CheckForLoggingIssues, self).generic_visit(node)

    def _find_name(self, node):
        """Return the fully qualified name or a Name or a Attribute."""
        if isinstance(node, ast.Name):
            return node.id
        elif (isinstance(node, ast.Attribute)
                and isinstance(node.value, (ast.Name, ast.Attribute))):

            obj_name = self._find_name(node.value)

            if obj_name is None:
                return None

            method_name = node.attr

            return obj_name + '.' + method_name
        elif isinstance(node, six.string_types):
            return node
        else:  # Could be Subscript, Call or many more
            return None

    def visit_Assign(self, node):
        """Look for 'LOG = logging.getLogger'

        This handles the simple case:
          name = [logging_module].getLogger(...)

        """
        attr_node_types = (ast.Name, ast.Attribute)

        if (len(node.targets) != 1
                or not isinstance(node.targets[0], attr_node_types)):
            # Say no to: "x, y = ..."
            return super(CheckForLoggingIssues, self).generic_visit(node)

        target_name = self._find_name(node.targets[0])

        if (isinstance(node.value, ast.BinOp) and
                isinstance(node.value.op, ast.Mod)):
            if (isinstance(node.value.left, ast.Call) and
                    isinstance(node.value.left.func, ast.Name)):

                # NOTE(dstanek): This is done to match cases like:
                # `msg = _('something %s') % x`
                node = ast.Assign(value=node.value.left)

        if not isinstance(node.value, ast.Call):

            # node.value must be a call to getLogger
            self.assignments.pop(target_name, None)

            return super(CheckForLoggingIssues, self).generic_visit(node)

        if (not isinstance(node.value.func, ast.Attribute)
                or not isinstance(node.value.func.value, attr_node_types)):

            # Function must be an attribute on an object like
            # logging.getLogger
            return super(CheckForLoggingIssues, self).generic_visit(node)

        object_name = self._find_name(node.value.func.value)
        func_name = node.value.func.attr

        if (object_name in self.logger_module_names
                and func_name == 'getLogger'):
            self.logger_names.append(target_name)

        return super(CheckForLoggingIssues, self).generic_visit(node)

    def visit_Call(self, node):
        """Look for the 'LOG.*' calls."""
        # obj.method
        if isinstance(node.func, ast.Attribute):
            obj_name = self._find_name(node.func.value)

            if isinstance(node.func.value, ast.Name):
                method_name = node.func.attr
            elif isinstance(node.func.value, ast.Attribute):
                obj_name = self._find_name(node.func.value)
                method_name = node.func.attr
            else:  # Could be Subscript, Call or many more
                return super(CheckForLoggingIssues, self).generic_visit(node)

            # If dealing with a logger the method can't be "warn".
            if obj_name in self.logger_names and method_name == 'warn':
                self.add_error(node.args[0])

        return super(CheckForLoggingIssues, self).generic_visit(node)


def factory(register):
    register(check_oslo_namespace_imports)
    register(CheckForLoggingIssues)
