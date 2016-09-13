# Copyright 2015 - Mirantis, Inc.
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

from oslo_utils import uuidutils
import six
import threading

from mistral import exceptions as exc
from mistral import utils
from mistral.workbook import types
from mistral.workbook.v2 import base
from mistral.workbook.v2 import task_defaults
from mistral.workbook.v2 import tasks


class WorkflowSpec(base.BaseSpec):
    # See http://json-schema.org

    _polymorphic_key = ('type', 'direct')

    _task_defaults_schema = task_defaults.TaskDefaultsSpec.get_schema(
        includes=None)

    _meta_schema = {
        "type": "object",
        "properties": {
            "type": types.WORKFLOW_TYPE,
            "task-defaults": _task_defaults_schema,
            "input": types.UNIQUE_STRING_OR_ONE_KEY_DICT_LIST,
            "output": types.NONEMPTY_DICT,
            "vars": types.NONEMPTY_DICT
        },
        "required": ["tasks"],
        "additionalProperties": False
    }

    def __init__(self, data):
        super(WorkflowSpec, self).__init__(data)

        self._name = data['name']
        self._description = data.get('description')
        self._tags = data.get('tags', [])
        self._type = data['type'] if 'type' in data else 'direct'
        self._input = utils.get_input_dict(data.get('input', []))
        self._output = data.get('output', {})
        self._vars = data.get('vars', {})

        self._task_defaults = self._spec_property(
            'task-defaults',
            task_defaults.TaskDefaultsSpec
        )

        # Inject 'type' here, so instantiate_spec function can recognize the
        # specific subclass of TaskSpec.
        for task in six.itervalues(self._data.get('tasks')):
            task['type'] = self._type

        self._tasks = self._spec_property('tasks', tasks.TaskSpecList)

    def validate_schema(self):
        super(WorkflowSpec, self).validate_schema()

        if not self._data.get('tasks'):
            raise exc.InvalidModelException(
                "Workflow doesn't have any tasks [data=%s]" % self._data
            )

        # Validate YAQL expressions.
        self.validate_yaql_expr(self._data.get('output', {}))
        self.validate_yaql_expr(self._data.get('vars', {}))

    def validate_semantics(self):
        super(WorkflowSpec, self).validate_semantics()

        # Distinguish workflow name from workflow UUID.
        if uuidutils.is_uuid_like(self._name):
            raise exc.InvalidModelException(
                "Workflow name cannot be in the format of UUID."
            )

    def _validate_task_link(self, task_name, allow_engine_cmds=True):
        valid_task = self._task_exists(task_name)

        if allow_engine_cmds:
            valid_task |= task_name in tasks.RESERVED_TASK_NAMES

        if not valid_task:
            raise exc.InvalidModelException(
                "Task '%s' not found." % task_name
            )

    def _task_exists(self, task_name):
        return self.get_tasks()[task_name] is not None

    def get_name(self):
        return self._name

    def get_description(self):
        return self._description

    def get_tags(self):
        return self._tags

    def get_type(self):
        return self._type

    def get_input(self):
        return self._input

    def get_output(self):
        return self._output

    def get_vars(self):
        return self._vars

    def get_task_defaults(self):
        return self._task_defaults

    def get_tasks(self):
        return self._tasks

    def get_task(self, name):
        return self._tasks[name]


class DirectWorkflowSpec(WorkflowSpec):
    _polymorphic_value = 'direct'

    _schema = {
        "properties": {
            "tasks": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    "^\w+$":
                        tasks.DirectWorkflowTaskSpec.get_schema(includes=None)
                }
            },
        }
    }

    def __init__(self, data):
        super(DirectWorkflowSpec, self).__init__(data)

        # Init simple dictionary based caches for inbound and
        # outbound task specifications. In fact, we don't need
        # any special cache implementations here because these
        # structures can't grow indefinitely.
        self.inbound_tasks_cache_lock = threading.RLock()
        self.inbound_tasks_cache = {}
        self.outbound_tasks_cache_lock = threading.RLock()
        self.outbound_tasks_cache = {}

    def validate_semantics(self):
        super(DirectWorkflowSpec, self).validate_semantics()

        # Check if there are start tasks.
        if not self.find_start_tasks():
            raise exc.DSLParsingException(
                'Failed to find start tasks in direct workflow. '
                'There must be at least one task without inbound transition.'
                '[workflow_name=%s]' % self._name
            )

        self._check_workflow_integrity()
        self._check_join_tasks()

    def _check_workflow_integrity(self):
        for t_s in self.get_tasks():
            out_task_names = self.find_outbound_task_names(t_s.get_name())

            for out_t_name in out_task_names:
                self._validate_task_link(out_t_name)

    def _check_join_tasks(self):
        join_tasks = [t for t in self.get_tasks() if t.get_join()]

        err_msgs = []

        for join_t in join_tasks:
            t_name = join_t.get_name()
            join_val = join_t.get_join()

            in_tasks = self.find_inbound_task_specs(join_t)

            if join_val == 'all':
                if len(in_tasks) == 0:
                    err_msgs.append(
                        "No inbound tasks for task with 'join: all'"
                        " [task_name=%s]" % t_name
                    )

                continue

            if join_val == 'one':
                join_val = 1

            if len(in_tasks) < join_val:
                err_msgs.append(
                    "Not enough inbound tasks for task with 'join'"
                    " [task_name=%s, join=%s, inbound_tasks=%s]" %
                    (t_name, join_val, len(in_tasks))
                )

        if len(err_msgs) > 0:
            raise exc.InvalidModelException('\n'.join(err_msgs))

    def find_start_tasks(self):
        return [
            t_s for t_s in self.get_tasks()
            if not self.has_inbound_transitions(t_s)
        ]

    def find_inbound_task_specs(self, task_spec):
        task_name = task_spec.get_name()

        with self.inbound_tasks_cache_lock:
            specs = self.inbound_tasks_cache.get(task_name)

        if specs is not None:
            return specs

        specs = [
            t_s for t_s in self.get_tasks()
            if self.transition_exists(t_s.get_name(), task_name)
        ]

        with self.inbound_tasks_cache_lock:
            self.inbound_tasks_cache[task_name] = specs

        return specs

    def find_outbound_task_specs(self, task_spec):
        task_name = task_spec.get_name()

        with self.outbound_tasks_cache_lock:
            specs = self.outbound_tasks_cache.get(task_name)

        if specs is not None:
            return specs

        specs = [
            t_s for t_s in self.get_tasks()
            if self.transition_exists(task_name, t_s.get_name())
        ]

        with self.outbound_tasks_cache_lock:
            self.outbound_tasks_cache[task_name] = specs

        return specs

    def has_inbound_transitions(self, task_spec):
        return len(self.find_inbound_task_specs(task_spec)) > 0

    def has_outbound_transitions(self, task_spec):
        return len(self.find_outbound_task_specs(task_spec)) > 0

    def find_outbound_task_names(self, task_name):
        t_names = set()

        for tup in self.get_on_error_clause(task_name):
            t_names.add(tup[0])

        for tup in self.get_on_success_clause(task_name):
            t_names.add(tup[0])

        for tup in self.get_on_complete_clause(task_name):
            t_names.add(tup[0])

        return t_names

    def transition_exists(self, from_task_name, to_task_name):
        t_names = self.find_outbound_task_names(from_task_name)

        return to_task_name in t_names

    def get_on_error_clause(self, t_name):
        result = self.get_tasks()[t_name].get_on_error()

        if not result:
            t_defaults = self.get_task_defaults()

            if t_defaults:
                result = self._remove_task_from_clause(
                    t_defaults.get_on_error(),
                    t_name
                )

        return result

    def get_on_success_clause(self, t_name):
        result = self.get_tasks()[t_name].get_on_success()

        if not result:
            t_defaults = self.get_task_defaults()

            if t_defaults:
                result = self._remove_task_from_clause(
                    t_defaults.get_on_success(),
                    t_name
                )

        return result

    def get_on_complete_clause(self, t_name):
        result = self.get_tasks()[t_name].get_on_complete()

        if not result:
            t_defaults = self.get_task_defaults()

            if t_defaults:
                result = self._remove_task_from_clause(
                    t_defaults.get_on_complete(),
                    t_name
                )

        return result

    @staticmethod
    def _remove_task_from_clause(on_clause, t_name):
        return list(filter(lambda tup: tup[0] != t_name, on_clause))


class ReverseWorkflowSpec(WorkflowSpec):
    _polymorphic_value = 'reverse'

    _schema = {
        "properties": {
            "tasks": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    "^\w+$":
                        tasks.ReverseWorkflowTaskSpec.get_schema(includes=None)
                }
            },
        }
    }

    def validate_semantics(self):
        super(ReverseWorkflowSpec, self).validate_semantics()

        self._check_workflow_integrity()

    def _check_workflow_integrity(self):
        for t_s in self.get_tasks():
            for req in self.get_task_requires(t_s):
                self._validate_task_link(req, allow_engine_cmds=False)

    def get_task_requires(self, task_spec):
        requires = set(task_spec.get_requires())

        defaults = self.get_task_defaults()

        if defaults:
            requires |= set(defaults.get_requires())

        requires.discard(task_spec.get_name())

        return list(requires)


class WorkflowSpecList(base.BaseSpecList):
    item_class = WorkflowSpec


class WorkflowListSpec(base.BaseListSpec):
    item_class = WorkflowSpec

    def get_workflows(self):
        return self.get_items()
