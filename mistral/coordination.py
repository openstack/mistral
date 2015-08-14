# Copyright 2015 Huawei Technologies Co., Ltd.
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

import six

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log
from oslo_service import threadgroup
from retrying import retry
import tooz.coordination

from mistral import utils


LOG = log.getLogger(__name__)

_SERVICE_COORDINATOR = None


class ServiceCoordinator(object):
    """Service coordinator.

    This class uses the `tooz` library to manage group membership.

    To ensure that the other agents know this agent is still alive,
    the `heartbeat` method should be called periodically.
    """

    def __init__(self, my_id=None):
        self._coordinator = None
        self._my_id = my_id or utils.get_process_identifier()
        self._started = False

    def start(self):
        backend_url = cfg.CONF.coordination.backend_url

        if backend_url:
            try:
                self._coordinator = tooz.coordination.get_coordinator(
                    backend_url,
                    self._my_id
                )

                self._coordinator.start()
                self._started = True

                LOG.info('Coordination backend started successfully.')
            except tooz.coordination.ToozError as e:
                self._started = False

                LOG.exception('Error connecting to coordination backend. '
                              '%s', six.text_type(e))

    def stop(self):
        if not self.is_active():
            return

        try:
            self._coordinator.stop()
        except tooz.coordination.ToozError:
            LOG.warning('Error connecting to coordination backend.')
        finally:
            self._coordinator = None
            self._started = False

    def is_active(self):
        return self._coordinator and self._started

    def heartbeat(self):
        if not self.is_active():
            # Re-connect.
            self.start()

        if not self.is_active():
            LOG.debug("Coordination backend didn't start.")
            return

        try:
            self._coordinator.heartbeat()
        except tooz.coordination.ToozError as e:
            LOG.exception('Error sending a heartbeat to coordination '
                          'backend. %s', six.text_type(e))

            self._started = False

    @retry(stop_max_attempt_number=5)
    def join_group(self, group_id):
        if not self.is_active() or not group_id:
            return

        try:
            join_req = self._coordinator.join_group(group_id)
            join_req.get()

            LOG.info(
                'Joined service group:%s, member:%s',
                group_id,
                self._my_id
            )

            return
        except tooz.coordination.MemberAlreadyExist:
            return
        except tooz.coordination.GroupNotCreated as e:
            create_grp_req = self._coordinator.create_group(group_id)

            try:
                create_grp_req.get()
            except tooz.coordination.GroupAlreadyExist:
                pass

            # Re-raise exception to join group again.
            raise e

    def leave_group(self, group_id):
        if self.is_active():
            self._coordinator.leave_group(group_id)

            LOG.info(
                'Left service group:%s, member:%s',
                group_id,
                self._my_id
            )

    def get_members(self, group_id):
        """Gets members of coordination group.

        ToozError exception must be handled when this function is invoded, we
        leave it to the invoker for the handling decision.
        """
        if not self.is_active():
            return []

        get_members_req = self._coordinator.get_members(group_id)
        try:
            members = get_members_req.get()

            LOG.debug('Members of group %s: %s', group_id, members)

            return members
        except tooz.coordination.GroupNotCreated:
            LOG.warning('Group %s does not exist.', group_id)

            return []


def cleanup_service_coordinator():
    """Intends to be used by tests to recreate service coordinator."""

    global _SERVICE_COORDINATOR

    _SERVICE_COORDINATOR = None


def get_service_coordinator(my_id=None):
    global _SERVICE_COORDINATOR

    if not _SERVICE_COORDINATOR:
        _SERVICE_COORDINATOR = ServiceCoordinator(my_id=my_id)
        _SERVICE_COORDINATOR.start()

    return _SERVICE_COORDINATOR


class Service(object):
    def __init__(self, group_type):
        self.group_type = group_type
        self._tg = None

    @lockutils.synchronized('service_coordinator')
    def register_membership(self):
        """Registers group membership.

        Because this method will be invoked on each service startup almost at
        the same time, so it must be synchronized, in case all the services
        are started within same process.
        """

        service_coordinator = get_service_coordinator()

        if service_coordinator.is_active():
            service_coordinator.join_group(self.group_type)

            self._tg = threadgroup.ThreadGroup()

            self._tg.add_timer(
                cfg.CONF.coordination.heartbeat_interval,
                service_coordinator.heartbeat
            )

    def stop(self):
        service_coordinator = get_service_coordinator()

        if service_coordinator.is_active():
            self._tg.stop()

            service_coordinator.stop()
