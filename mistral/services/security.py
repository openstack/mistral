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

from datetime import timedelta

from keystoneauth1 import exceptions as ks_exc
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import timeutils

from mistral import context as auth_ctx
from mistral import exceptions as exc
from mistral.utils.openstack import keystone


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

# Make sure to import 'auth_enable' option before using it.
# TODO(rakhmerov): Try to find a better solution.
CONF.import_opt('auth_enable', 'mistral.config', group='pecan')
CONF.import_opt('use_trusts', 'mistral.config', group='engine')


DEFAULT_PROJECT_ID = "<default-project>"


def get_project_id():
    if CONF.pecan.auth_enable and auth_ctx.has_ctx():
        return auth_ctx.ctx().project_id
    else:
        return DEFAULT_PROJECT_ID


def create_trust():
    ctx = auth_ctx.ctx()

    # Create a keystone client on behalf of end-user
    client = keystone.client()

    trustee_id = keystone.client_for_admin().session.get_user_id()

    try:
        return client.trusts.create(
            trustor_user=ctx.user_id,
            trustee_user=trustee_id,
            impersonation=True,
            role_names=ctx.roles,
            project=ctx.project_id,
        )
    except ks_exc.Forbidden as e:
        raise exc.NotAllowedException(
            "Keystone refused to create a trust: %s. Note that a trust "
            "cannot be created from a trust-scoped token unless that trust "
            "has allow_redelegation enabled." % e
        )


def create_context(trust_id, project_id):
    """Creates Mistral security context.

    :param trust_id: Trust Id.
    :param project_id: Project Id.
    :return: Mistral security context.
    """

    if CONF.pecan.auth_enable:
        client = keystone.client_for_trusts(trust_id)

        expires_at = None

        if client.session:
            # Method get_token is deprecated, using get_auth_headers.
            token = client.session.get_auth_headers().get('X-Auth-Token')
            user_id = client.session.get_user_id()
            access = client.session.auth.get_access(client.session)
            expires_at = access.expires.isoformat()
        else:
            token = client.auth_token
            user_id = client.user_id

        return auth_ctx.MistralContext(
            user_id=user_id,
            project_id=project_id,
            auth_token=token,
            is_trust_scoped=True,
            trust_id=trust_id,
            expires_at=expires_at,
        )

    return auth_ctx.MistralContext(
        user_id=None, project_id=None, auth_token=None, is_admin=True
    )


def delete_trust(trust_id=None):
    if not trust_id:
        # Try to retrieve trust from context.
        if auth_ctx.has_ctx():
            trust_id = auth_ctx.ctx().trust_id

    if not trust_id:
        return

    keystone_client = keystone.client_for_trusts(trust_id)

    try:
        keystone_client.trusts.delete(trust_id)
    except Exception as e:
        LOG.warning("Failed to delete trust [id=%s]: %s", trust_id, e)


def add_trust_id(secure_object_values):
    if cfg.CONF.pecan.auth_enable:
        trust = create_trust()
        secure_object_values.update({'trust_id': trust.id})


def add_execution_trust():
    if not (CONF.pecan.auth_enable and CONF.engine.use_trusts):
        return

    ctx = auth_ctx.ctx()

    if ctx.trust_id:
        return

    try:
        trust = create_trust()
    except Exception as e:
        LOG.warning(
            "Failed to create a trust, the workflow execution will use the "
            "caller's token and stop working when it expires: %s",
            e,
        )
        return

    ctx.trust_id = trust.id
    ctx.is_trust_scoped = True
    ctx.execution_trust = True


def delete_execution_trust():
    if not auth_ctx.has_ctx():
        return

    ctx = auth_ctx.ctx()

    if ctx.execution_trust:
        delete_trust(ctx.trust_id)
        ctx.trust_id = None
        ctx.is_trust_scoped = False
        ctx.execution_trust = False


def refresh_context(ctx, margin=timedelta(minutes=5)):
    if not (CONF.pecan.auth_enable and ctx.trust_id and ctx.is_trust_scoped):
        return ctx

    if ctx.expires_at:
        expires_at = timeutils.normalize_time(
            timeutils.parse_isotime(ctx.expires_at)
        )

        if expires_at - margin > timeutils.utcnow():
            return ctx

    new_ctx = create_context(ctx.trust_id, ctx.project_id)

    ctx.auth_token = new_ctx.auth_token
    ctx.user_id = new_ctx.user_id
    ctx.expires_at = new_ctx.expires_at
    ctx.service_catalog = None

    return ctx


def on_workflow_complete(wf_ex):
    trust_id = (wf_ex.runtime_context or {}).get('execution_trust_id')

    if trust_id:
        from mistral.engine import post_tx_queue

        post_tx_queue.register_operation(delete_trust, args=[trust_id])
