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

from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.lang import parser as spec_parser
from mistral import utils
from mistral.workflow import states
from oslo_log import log as logging


STD_WF_PATH = 'resources/workflows'
LOG = logging.getLogger(__name__)


def register_standard_workflows(run_in_tx=True):
    LOG.debug("Registering standard workflows...")

    workflow_paths = utils.get_file_list(STD_WF_PATH)

    for wf_path in workflow_paths:
        workflow_definition = open(wf_path).read()

        create_workflows(
            workflow_definition,
            scope='public',
            is_system=True,
            run_in_tx=run_in_tx,
            namespace=''
        )


def _clear_system_workflow_db():
    db_api.delete_workflow_definitions(is_system=True)


def sync_db():
    LOG.debug("Syncing db...")

    with db_api.transaction():
        _clear_system_workflow_db()

        register_standard_workflows(run_in_tx=False)


def create_workflows(definition, scope='private', is_system=False,
                     run_in_tx=True, namespace=''):
    LOG.debug("Creating workflows...")

    wf_list_spec = spec_parser.get_workflow_list_spec_from_yaml(
        definition,
        validate=True
    )
    db_wfs = []

    if run_in_tx:
        with db_api.transaction():
            _append_all_workflows(
                definition,
                is_system,
                scope,
                namespace,
                wf_list_spec,
                db_wfs
            )
    else:
        _append_all_workflows(
            definition,
            is_system,
            scope,
            namespace,
            wf_list_spec,
            db_wfs
        )

    return db_wfs


def _append_all_workflows(definition, is_system, scope, namespace,
                          wf_list_spec, db_wfs):
    for wf_spec in wf_list_spec.get_workflows():
        db_wfs.append(
            _create_workflow(
                wf_spec,
                definition,
                scope,
                namespace,
                is_system
            )
        )


def update_workflows(definition, scope='private', identifier=None,
                     namespace=''):
    LOG.debug("Updating workflows")

    wf_list_spec = spec_parser.get_workflow_list_spec_from_yaml(
        definition, validate=True
    )
    wfs = wf_list_spec.get_workflows()

    if identifier and len(wfs) > 1:
        raise exc.InputException(
            "More than one workflows are not supported for "
            "update with identifier. [identifier: %s]" %
            identifier
        )

    db_wfs = []

    with db_api.transaction():
        for wf_spec in wf_list_spec.get_workflows():
            db_wfs.append(_update_workflow(
                wf_spec,
                definition,
                scope,
                namespace=namespace,
                identifier=identifier
            ))

    return db_wfs


def update_workflow_execution_env(wf_ex, env):
    if not env:
        return wf_ex

    if wf_ex.state not in [states.IDLE, states.PAUSED, states.ERROR]:
        raise exc.NotAllowedException(
            'Updating env to workflow execution is only permitted if '
            'it is in IDLE, PAUSED, or ERROR state.'
        )

    wf_ex.params['env'] = utils.merge_dicts(wf_ex.params['env'], env)

    return wf_ex


def _get_workflow_values(wf_spec, definition, scope, namespace=None,
                         is_system=False):
    values = {
        'name': wf_spec.get_name(),
        'tags': wf_spec.get_tags(),
        'definition': definition,
        'spec': wf_spec.to_dict(),
        'scope': scope,
        'namespace': namespace,
        'is_system': is_system
    }

    return values


def _create_workflow(wf_spec, definition, scope, namespace, is_system):
    return db_api.create_workflow_definition(
        _get_workflow_values(wf_spec, definition, scope, namespace, is_system)
    )


def _update_workflow(wf_spec, definition, scope, identifier=None,
                     namespace=''):
    values = _get_workflow_values(wf_spec, definition, scope, namespace)

    return db_api.update_workflow_definition(
        identifier if identifier else values['name'],
        values
    )
