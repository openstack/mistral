# -*- coding: utf-8 -*-
#
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

from pecan import hooks


class ContentTypeHook(hooks.PecanHook):
    def __init__(self, content_type, methods=['GET']):
        """Content type hook.

        This hook is needed for changing content type of
        responses but only for some HTTP methods. This is kind of
        'hack' but it seems impossible using pecan/WSME to set different
        content types on request and response.

        :param content_type: Content-Type that response should has.
        :type content_type: str
        :param methods: HTTP methods that should have response
        with given content_type.
        :type methods: list
        """
        self.content_type = content_type
        self.methods = methods

    def after(self, state):
        if state.request.method in self.methods:
            state.response.content_type = self.content_type
