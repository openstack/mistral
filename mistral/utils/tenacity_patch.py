#  Copyright 2020 - Nokia Corporation
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
import re

from tenacity.retry import retry_if_exception


# Copied this class from tenacity version 5.0.1 since this
# doesn't exists in version 4.12.0 and we cannot update the upper
# constrains file for rocky since it is too old and might break things
# See https://review.opendev.org/#/c/710204/
class retry_if_exception_message(retry_if_exception):
    """Retries if an exception message equals or matches."""

    def __init__(self, message=None, match=None):
        if message and match:
            raise TypeError(
                "{}() takes either 'message' or 'match', not both".format(
                    self.__class__.__name__))

        # set predicate
        if message:
            def message_fnc(exception):
                return message == str(exception)
            predicate = message_fnc
        elif match:
            prog = re.compile(match)

            def match_fnc(exception):
                return prog.match(str(exception))
            predicate = match_fnc
        else:
            raise TypeError(
                "{}() missing 1 required argument 'message' or 'match'".
                format(self.__class__.__name__))

        super(retry_if_exception_message, self).__init__(predicate)
