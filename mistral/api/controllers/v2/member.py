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
import uuid

from oslo_config import cfg
from oslo_log import log as logging
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from mistral.api.controllers import resource
from mistral.api.controllers.v2 import types
from mistral.db.v2 import api as db_api
from mistral import exceptions as exc
from mistral.utils import rest_utils


LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class Member(resource.Resource):
    id = types.uuid
    resource_id = wtypes.text
    resource_type = wtypes.text
    project_id = wtypes.text
    member_id = wtypes.text
    status = wtypes.Enum(str, 'pending', 'accepted', 'rejected')
    created_at = wtypes.text
    updated_at = wtypes.text

    @classmethod
    def sample(cls):
        return cls(
            id=str(uuid.uuid4()),
            resource_id=str(uuid.uuid4()),
            resource_type='workflow',
            project_id='40a908dbddfe48ad80a87fb30fa70a03',
            member_id='a7eb669e9819420ea4bd1453e672c0a7',
            status='accepted',
            created_at='1970-01-01T00:00:00.000000',
            updated_at='1970-01-01T00:00:00.000000'
        )


class Members(resource.ResourceList):
    members = [Member]

    @classmethod
    def sample(cls):
        return cls(members=[Member.sample()])


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
    @wsme_pecan.wsexpose(Member, wtypes.text)
    def get(self, member_id):
        """Shows resource member details."""
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

        return Member.from_dict(member_dict)

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(Members)
    def get_all(self):
        """Return all members with whom the resource has been shared."""
        LOG.info(
            "Fetch resource members [resource_id=%s, resource_type=%s].",
            self.resource_id,
            self.type
        )

        db_members = db_api.get_resource_members(
            self.resource_id,
            self.type
        )
        members = [Member.from_dict(member.to_dict()) for member in db_members]

        return Members(members=members)

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(Member, body=Member, status_code=201)
    def post(self, member_info):
        """Shares the resource to a new member."""
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

        return Member.from_dict(db_member.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(Member, wtypes.text, body=Member)
    def put(self, member_id, member_info):
        """Sets the status for a resource member."""
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

        return Member.from_dict(db_member.to_dict())

    @rest_utils.wrap_pecan_controller_exception
    @auth_enable_check
    @wsme_pecan.wsexpose(None, wtypes.text, status_code=204)
    def delete(self, member_id):
        """Deletes a member from the member list of a resource."""
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
