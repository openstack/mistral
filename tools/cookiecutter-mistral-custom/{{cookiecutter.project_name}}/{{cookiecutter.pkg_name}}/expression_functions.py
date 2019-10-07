#  Copyright 2019 - Nokia Corporation
#
#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.


from time import time
from uuid import UUID
from uuid import uuid5


def my_function_(context):
    """Generate a UUID using the execution ID and the clock."""
    # fetch the current workflow execution ID found in the context
    execution_id = context['__execution']['id']

    time_str = str(time())
    execution_uuid = UUID(execution_id)
    return uuid5(execution_uuid, time_str)
