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

import mistral.openstack.common.exception as ex


class MistralException(ex.Error):
    """Base Exception for the project

    To correctly use this class, inherit from it and define
    a 'message' and 'code' properties.
    """
    message = "An unknown exception occurred"
    code = "UNKNOWN_EXCEPTION"

    def __str__(self):
        return self.message

    def __init__(self, message=message):
        self.message = message
        super(MistralException, self).__init__(
            '%s: %s' % (self.code, self.message))


class DataAccessException(MistralException):
    def __init__(self, message=None):
        super(DataAccessException, self).__init__(message)
        if message:
            self.message = message


class DBDuplicateEntry(MistralException):
    message = "Database object already exists"
    code = "DB_DUPLICATE_ENTRY"

    def __init__(self, message=None):
        super(DBDuplicateEntry, self).__init__(message)
        if message:
            self.message = message


class ActionException(MistralException):
    code = "ACTION_ERROR"

    def __init__(self, message=None):
        super(MistralException, self).__init__(message)
        if message:
            self.message = message


class InvalidActionException(MistralException):
    def __init__(self, message=None):
        super(InvalidActionException, self).__init__(message)
        if message:
            self.message = message


class ActionRegistrationException(MistralException):
    message = "Failed to register action"
    code = "ACTION_REGISTRATION_ERROR"

    def __init__(self, message=None):
        super(ActionRegistrationException, self).__init__(message)
        if message:
            self.message = message


class EngineException(MistralException):
    code = "ENGINE_ERROR"

    def __init__(self, message=None):
        super(EngineException, self).__init__(message)
        if message:
            self.message = message


class ApplicationContextNotFoundException(MistralException):
    message = "Application context not found"
    code = "APP_CTX_NOT_FOUND_ERROR"

    def __init__(self, message=None):
        super(ApplicationContextNotFoundException, self).__init__(message)
        if message:
            self.message = message


class InvalidModelException(MistralException):
    message = "Wrong entity definition"
    code = "INVALID_MODEL_EXCEPTION"

    def __init__(self, message=None):
        super(InvalidModelException, self).__init__(message)
        if message:
            self.message = message
