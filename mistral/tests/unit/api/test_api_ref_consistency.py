# Copyright 2024 - OpenStack Foundation
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

"""Consistency checks between the code and the hand-written API reference.

Unlike the rendered docs, ``os-api-ref`` (the ``api-ref/`` tree) is maintained
entirely by hand: the ``.inc`` files and ``parameters.yaml`` are not generated
from the controllers or the WSME resources. That makes them easy to forget
when the API changes. These tests do not *generate* the reference; they assert
that it has not silently drifted from the code:

* every WSME resource attribute is documented somewhere in the reference;
* every top-level v2 controller is documented;
* ``parameters.yaml`` has no dangling references and no unused entries.

When you intentionally add/rename a field or endpoint, update the api-ref in
the same change (and, for the rare deliberate omission, the small allow-lists
below). The point is to make that an explicit, reviewable decision instead of
an accident.
"""

import os
import re

from oslotest import base

from mistral.api.controllers import resource as resource_base
from mistral.api.controllers.v2 import resources
from mistral.api.controllers.v2 import root as v2_root


# api-ref/source lives at the repository root, four levels above this file
# (mistral/tests/unit/api/).
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir,
                 os.pardir)
)
_API_REF_SOURCE = os.path.join(_REPO_ROOT, 'api-ref', 'source')
_PARAMETERS_YAML = os.path.join(_API_REF_SOURCE, 'parameters.yaml')

# A documented parameter row looks like "  - <field>: <parameters.yaml key>".
_PARAM_ROW_RE = re.compile(r'^\s+-\s+(?P<field>[A-Za-z0-9_]+):'
                           r'\s*(?P<key>[A-Za-z0-9_]+)\s*$')

# Resource classes that intentionally have no public api-ref entry.
_IGNORED_RESOURCES = frozenset([
    # Base/utility classes, not concrete API resources.
    'Resource',
    'ResourceList',
    # The /v2/services maintenance endpoint is an internal/operator API and is
    # deliberately not part of the public reference.
    'Service',
    'Services',
])

# Fields that are accepted as undocumented on *any* resource. Tracked debt --
# shrink this set, don't grow it.
#   * "next": the pagination link present on every ResourceList response; it is
#     part of the list contract but is not yet broken out in the reference.
_GLOBAL_UNDOCUMENTED_FIELDS = frozenset(['next'])

# Known, accepted gaps: nested execution-report fields that are not yet broken
# out in the api-ref report section. Tracked debt -- shrink this set, don't
# grow it. Each entry is (resource class name -> set of field names).
_KNOWN_UNDOCUMENTED = {
    'ActionExecutionReportEntry': {'last_heartbeat'},
    'WorkflowExecutionReportEntry': {'task_executions'},
    'TaskExecutionReportEntry': {'retry_count', 'workflow_executions'},
    'ExecutionReportStatistics': {
        'running_tasks_count',
        'success_tasks_count',
        'error_tasks_count',
        'idle_tasks_count',
        'paused_tasks_count',
        'total_tasks_count',
        'estimated_time',
    },
}


def _read_inc_text():
    """Return the concatenated text of every api-ref .inc file."""
    chunks = []

    for name in sorted(os.listdir(_API_REF_SOURCE)):
        if name.endswith('.inc'):
            with open(os.path.join(_API_REF_SOURCE, name)) as fh:
                chunks.append(fh.read())

    return '\n'.join(chunks)


def _documented_fields_and_param_keys():
    """Parse rest_parameters rows from every .inc file.

    Returns a tuple ``(fields, keys)`` where ``fields`` is the set of
    documented attribute names (left-hand side) and ``keys`` is the set of
    referenced parameters.yaml keys (right-hand side).
    """
    fields = set()
    keys = set()

    for name in os.listdir(_API_REF_SOURCE):
        if not name.endswith('.inc'):
            continue

        with open(os.path.join(_API_REF_SOURCE, name)) as fh:
            for line in fh:
                match = _PARAM_ROW_RE.match(line)

                if match:
                    fields.add(match.group('field'))
                    keys.add(match.group('key'))

    return fields, keys


def _resource_classes():
    """Yield (name, class) for every concrete WSME resource in resources.py."""
    for name in dir(resources):
        obj = getattr(resources, name)

        if not isinstance(obj, type):
            continue

        # Only classes actually defined in resources.py (skip imports), that
        # are WSME resources.
        if obj.__module__ != resources.__name__:
            continue

        if not issubclass(obj, resource_base.Resource):
            continue

        if name in _IGNORED_RESOURCES:
            continue

        yield name, obj


class APIRefConsistencyTest(base.BaseTestCase):
    """Guard against drift between the v2 API code and api-ref/."""

    def setUp(self):
        super(APIRefConsistencyTest, self).setUp()

        if not os.path.isdir(_API_REF_SOURCE):
            self.skipTest('api-ref source tree not available (running from an '
                          'installed package rather than the repo checkout)')

    def test_every_resource_field_is_documented(self):
        documented, _ = _documented_fields_and_param_keys()

        missing = {}

        for name, cls in _resource_classes():
            allowed = _KNOWN_UNDOCUMENTED.get(name, set())

            undocumented = {
                field for field in cls.get_fields()
                if field not in documented
                and field not in allowed
                and field not in _GLOBAL_UNDOCUMENTED_FIELDS
            }

            if undocumented:
                missing[name] = sorted(undocumented)

        self.assertEqual(
            {}, missing,
            'These WSME resource attributes are not documented anywhere in '
            'api-ref/source/*.inc. Document them (add a rest_parameters row '
            'and a parameters.yaml entry) in the same change, or -- if the '
            'omission is deliberate -- extend the allow-lists in this test '
            'with a justification:\n%s' % missing
        )

    def test_every_top_level_controller_is_documented(self):
        inc_text = _read_inc_text()

        missing = []

        for attr in vars(v2_root.Controller):
            if attr.startswith('_'):
                continue

            value = vars(v2_root.Controller)[attr]

            # Skip the index() method and anything that is not a mounted
            # sub-controller instance.
            if callable(value):
                continue

            path = '/v2/%s' % attr

            if path not in inc_text:
                missing.append(path)

        self.assertEqual(
            [], sorted(missing),
            'These top-level v2 endpoints have no `.. rest_method:: ... '
            '%s ...` entry in api-ref. Add an .inc section for them.'
            % sorted(missing)
        )

    def test_parameters_yaml_has_no_dangling_references(self):
        import yaml

        with open(_PARAMETERS_YAML) as fh:
            defined = set(yaml.safe_load(fh).keys())

        _, referenced = _documented_fields_and_param_keys()

        dangling = referenced - defined

        self.assertEqual(
            set(), dangling,
            'These parameters.yaml keys are referenced from .inc files '
            'but are not defined in parameters.yaml: %s' % sorted(dangling)
        )

    def test_parameters_yaml_has_no_unused_entries(self):
        import yaml

        with open(_PARAMETERS_YAML) as fh:
            defined = set(yaml.safe_load(fh).keys())

        _, referenced = _documented_fields_and_param_keys()

        unused = defined - referenced

        self.assertEqual(
            set(), unused,
            'These parameters.yaml entries are defined but never referenced '
            'from any .inc file. Remove them or wire them up: %s'
            % sorted(unused)
        )
