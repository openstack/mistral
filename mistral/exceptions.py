# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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


class Error(Exception):
    def __init__(self, message=None):
        super(Error, self).__init__(message)


class MistralException(Error):
    """Base Exception for the project

    To correctly use this class, inherit from it and define
    a 'message' and 'http_code' properties.
    """
    message = "An unknown exception occurred"
    http_code = 500

    @property
    def code(self):
        """This is here for webob to read.

        https://github.com/Pylons/webob/blob/master/webob/exc.py
        """
        return self.http_code

    def __str__(self):
        return self.message

    def __init__(self, message=None):
        if message is not None:
            self.message = message
        super(MistralException, self).__init__(
            '%d: %s' % (self.http_code, self.message))


class DBException(MistralException):
    http_code = 400


class DataAccessException(MistralException):
    http_code = 400


class NotFoundException(MistralException):
    http_code = 404
    message = "Object not found"


class DBDuplicateEntry(MistralException):
    http_code = 409
    message = "Database object already exists"


class ActionException(MistralException):
    http_code = 400


class InvalidActionException(MistralException):
    http_code = 400


class ActionRegistrationException(MistralException):
    message = "Failed to register action"


class EngineException(MistralException):
    http_code = 500


class WorkflowException(MistralException):
    http_code = 400


class InputException(MistralException):
    http_code = 400


class ApplicationContextNotFoundException(MistralException):
    http_code = 400
    message = "Application context not found"


class DSLParsingException(MistralException):
    http_code = 400


class YaqlEvaluationException(DSLParsingException):
    http_code = 400
    message = "Can not evaluate YAQL expression"


class InvalidModelException(DSLParsingException):
    http_code = 400
    message = "Wrong entity definition"


class InvalidResultException(MistralException):
    http_code = 400
    message = "Unable to parse result"
