# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - Huawei Technologies Co. Ltd
# Copyright 2016 - Brocade Communications Systems, Inc.
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

import inspect
import threading

from oslo_serialization import jsonutils


def to_json_str(obj):
    """Serializes an object into a JSON string.

    :param obj: Object to serialize.
    :return: JSON string.
    """

    if obj is None:
        return None

    def _fallback(value):
        if inspect.isgenerator(value):
            result = list(value)

            # The result of the generator call may be again not primitive
            # so we need to call "to_primitive" again with the same fallback
            # function. Note that the endless recursion here is not a problem
            # because "to_primitive" limits the depth for custom classes,
            # if they are present in the object graph being traversed.
            return jsonutils.to_primitive(
                result,
                convert_instances=True,
                fallback=_fallback
            )

        return value

    # We need to convert the root of the given object graph into
    # a primitive by hand so that we also enable conversion of
    # object of custom classes into primitives. Otherwise, they are
    # ignored by the "json" lib.
    return jsonutils.dumps(
        jsonutils.to_primitive(obj, convert_instances=True, fallback=_fallback)
    )


def from_json_str(json_str):
    """Reconstructs an object from a JSON string.

    :param json_str: A JSON string.
    :return: Deserialized object.
    """

    if json_str is None:
        return None

    return jsonutils.loads(json_str)


class ThreadWithException(threading.Thread):
    """Thread capturing exception"""

    def run(self):
        self.exception = None
        try:
            super().run()
        except Exception as e:
            self.exception = e

    def join(self, *args, **kwargs):
        super().join(*args, **kwargs)
        if self.exception:
            raise self.exception
