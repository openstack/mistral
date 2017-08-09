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

from oslo_config import cfg
from oslo_log import log as logging

from mistral import context as auth_ctx
from mistral.utils.openstack import keystone


LOG = logging.getLogger(__name__)
CONF = cfg.CONF

# Make sure to import 'auth_enable' option before using it.
# TODO(rakhmerov): Try to find a better solution.
CONF.import_opt('auth_enable', 'mistral.config', group='pecan')


DEFAULT_PROJECT_ID = "<default-project>"


def get_project_id():
    if CONF.pecan.auth_enable and auth_ctx.has_ctx():
        return auth_ctx.ctx().project_id
    else:
        return DEFAULT_PROJECT_ID


def create_trust():
    client = keystone.client()

    ctx = auth_ctx.ctx()

    trustee_id = keystone.client_for_admin().session.get_user_id()

    return client.trusts.create(
        trustor_user=client.user_id,
        trustee_user=trustee_id,
        impersonation=True,
        role_names=ctx.roles,
        project=ctx.project_id
    )


def create_context(trust_id, project_id):
    """Creates Mistral security context.

    :param trust_id: Trust Id.
    :param project_id: Project Id.
    :return: Mistral security context.
    """

    if CONF.pecan.auth_enable:
        client = keystone.client_for_trusts(trust_id)

        if client.session:
            # Method get_token is deprecated, using get_auth_headers.
            token = client.session.get_auth_headers().get('X-Auth-Token')
            user_id = client.session.get_user_id()
        else:
            token = client.auth_token
            user_id = client.user_id

        return auth_ctx.MistralContext(
            user=user_id,
            tenant=project_id,
            auth_token=token,
            is_trust_scoped=True,
            trust_id=trust_id,
        )

    return auth_ctx.MistralContext(
        user=None,
        tenant=None,
        auth_token=None,
        is_admin=True
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
        secure_object_values.update({
            'trust_id': trust.id
        })
