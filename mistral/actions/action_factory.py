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

from oslo_utils import importutils


def construct_action_class(action_class_str, attributes):
    # Rebuild action class and restore attributes.
    action_class = importutils.import_class(action_class_str)

    unique_action_class = type(
        action_class.__name__,
        (action_class,),
        attributes
    )

    return unique_action_class
