# Copyright 2014 - Mirantis, Inc.
# Copyright 2017 - Brocade Communications Systems, Inc.
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

import abc
import six


@six.add_metaclass(abc.ABCMeta)
class EventEngine(object):
    """Action event trigger interface."""

    @abc.abstractmethod
    def create_event_trigger(self, trigger, events):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_event_trigger(self, trigger):
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_event_trigger(self, trigger, events):
        raise NotImplementedError()
