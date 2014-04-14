# -*- coding: utf-8 -*-
#
# Copyright 2013 - Mirantis, Inc.
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

#TODO(rakhmerov): Remove this module after refactoring.

"""Valid action types."""

ECHO = 'ECHO'
REST_API = 'REST_API'
OSLO_RPC = 'OSLO_RPC'
MISTRAL_REST_API = 'MISTRAL_REST_API'
SEND_EMAIL = "SEND_EMAIL"
SSH = "SSH"

_ALL = [ECHO, REST_API, OSLO_RPC, MISTRAL_REST_API, SEND_EMAIL, SSH]


def is_valid(action_type):
    return action_type in _ALL
