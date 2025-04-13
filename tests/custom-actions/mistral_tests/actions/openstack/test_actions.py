# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo_log import log

LOG = log.getLogger(__name__)


# You can inherit from the Nova client class.
class NovaTestClient(object):

    def __init__(self, *args, **kwargs):
        # I just ignore them. But you can do anything with them.

        self.servers = Servers()


class Servers(object):

    def create(self, name, image, flavor, key_name, security_groups, nics):
        LOG.info(locals())

        return {
            'id': str(image)
        }
