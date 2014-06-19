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

from oslo.config import cfg

from mistral import context
from mistral.db import api as db_api
from mistral.utils.openstack import keystone


CONF = cfg.CONF


def create_trust(workbook):
    client = keystone.client()

    ctx = context.ctx()

    trustee_id = keystone.client_for_admin(
        CONF.keystone_authtoken.admin_tenant_name).user_id

    trust = client.trusts.create(trustor_user=client.user_id,
                                 trustee_user=trustee_id,
                                 impersonation=True,
                                 role_names=ctx.roles,
                                 project=ctx.project_id)

    return db_api.workbook_update(workbook['name'],
                                  {'trust_id': trust.id,
                                   'project_id': ctx.project_id})


def create_context(workbook):
    if 'trust_id' not in workbook:
        return

    if CONF.pecan.auth_enable:
        client = keystone.client_for_trusts(workbook['trust_id'])

        return context.MistralContext(
            user_id=client.user_id,
            project_id=workbook['project_id'],
            auth_token=client.auth_token
        )
    else:
        return context.MistralContext(
            user_id=None,
            project_id=None,
            auth_token=None
        )


def delete_trust(workbook):
    if 'trust_id' not in workbook:
        return

    keystone_client = keystone.client_for_trusts(workbook['trust_id'])
    keystone_client.trusts.delete(workbook.trust_id)
