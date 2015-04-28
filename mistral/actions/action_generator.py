# Copyright 2014 - Mirantis, Inc.
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


class ActionGenerator(object):
    """Action generator.

    Action generator uses some data to build Action classes
    dynamically.
    """
    @abc.abstractmethod
    def create_actions(self, *args, **kwargs):
        """Constructs classes of needed action.

        return: list of actions dicts containing name, class,
        description and parameter info.
        """
        pass
