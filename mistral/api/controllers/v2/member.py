# Copyright 2015 Huawei Technologies Co., Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import functools

from oslo_config import cfg
from oslo_log import log as logging
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api import access_control as acl
from mistral.api.controllers.v2 import resources
from mistral import context
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def auth_enable_check(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if not CONF.pecan.auth_enable:
            msg = ("Resource sharing feature can only be supported with "
                   "authentication enabled.")
            raise exc.WorkflowException(msg)
        return func(*args, **kwargs)

    return wrapped


class MembersController(rest.RestController):
    def __init__(self, type, resource_id):
        self.type = type
        self.resource_id = resource_id

        super(MembersController, self).__init__()

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(resources.Member, wtypes.text)
    def get(self, member_id):
        """Shows resource member details."""
        acl.enforce('members:get', context.ctx())

        LOG.info(
            "Fetch resource member [resource_id=%s, resource_type=%s, "
            "member_id=%s].",
            self.resource_id,
            self.type,
            member_id
        )

        member_dict = db_api.get_resource_member(
            self.resource_id,
            self.type,
            member_id
        ).to_dict()

        return resources.Member.from_dict(member_dict)

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(resources.Members)
    def get_all(self):
        """Return all members with whom the resource has been shared."""
        acl.enforce('members:list', context.ctx())

        LOG.info(
            "Fetch resource members [resource_id=%s, resource_type=%s].",
            self.resource_id,
            self.type
        )

        db_members = db_api.get_resource_members(
            self.resource_id,
            self.type
        )
        members = [
            resources.Member.from_dict(member.to_dict())
            for member in db_members
        ]

        return resources.Members(members=members)

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(
        resources.Member,
        body=resources.Member,
        status_code=201
    )
    def post(self, member_info):
        """Shares the resource to a new member."""
        acl.enforce('members:create', context.ctx())

        LOG.info(
            "Share resource to a member. [resource_id=%s, "
            "resource_type=%s, member_info=%s].",
            self.resource_id,
            self.type,
            member_info
        )

        if not member_info.member_id:
            msg = "Member id must be provided."
            raise exc.WorkflowException(msg)

        wf_db = db_api.get_workflow_definition(self.resource_id)

        if wf_db.scope != 'private':
            msg = "Only private resource could be shared."
            raise exc.WorkflowException(msg)

        resource_member = {
            'resource_id': self.resource_id,
            'resource_type': self.type,
            'member_id': member_info.member_id,
            'status': 'pending'
        }

        db_member = db_api.create_resource_member(resource_member)

        return resources.Member.from_dict(db_member.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(resources.Member, wtypes.text, body=resources.Member)
    def put(self, member_id, member_info):
        """Sets the status for a resource member."""
        acl.enforce('members:update', context.ctx())

        LOG.info(
            "Update resource member status. [resource_id=%s, "
            "member_id=%s, member_info=%s].",
            self.resource_id,
            member_id,
            member_info
        )

        if not member_info.status:
            msg = "Status must be provided."
            raise exc.WorkflowException(msg)

        db_member = db_api.update_resource_member(
            self.resource_id,
            self.type,
            member_id,
            {'status': member_info.status}
        )

        return resources.Member.from_dict(db_member.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, member_id):
        """Deletes a member from the member list of a resource."""
        acl.enforce('members:delete', context.ctx())

        LOG.info(
            "Delete resource member. [resource_id=%s, "
            "resource_type=%s, member_id=%s].",
            self.resource_id,
            self.type,
            member_id
        )

        db_api.delete_resource_member(
            self.resource_id,
            self.type,
            member_id
        )
