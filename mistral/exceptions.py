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


# TODO(rakhmerov): Can we make one parent for errors and exceptions?

class MistralError(Exception):
    """Mistral specific error.

    Reserved for situations that can't be automatically handled. When it occurs
    it signals that there is a major environmental problem like invalid startup
    configuration or implementation problem (e.g. some code doesn't take care
    of certain corner cases). From architectural perspective it's pointless to
    try to handle this type of problems except doing some finalization work
    like transaction rollback, deleting temporary files etc.
    """

    message = "An unknown error occurred"
    http_code = 500

    def __init__(self, message=None):
        if message is not None:
            self.message = message

        super(MistralError, self).__init__(
            '%d: %s' % (self.http_code, self.message))

    @property
    def code(self):
        """This is here for webob to read.

        https://github.com/Pylons/webob/blob/master/webob/exc.py
        """
        return self.http_code

    def __str__(self):
        return self.message


class MistralException(Exception):
    """Mistral specific exception.

    Reserved for situations that are not critical for program continuation.
    It is possible to recover from this type of problems automatically and
    continue program execution. Such problems may be related with invalid user
    input (such as invalid syntax) or temporary environmental problems.

    In case if an instance of a certain exception type bubbles up to API layer
    then this type of exception it must be associated with an http code so it's
    clear how to represent it for a client.

    To correctly use this class, inherit from it and define a 'message' and
    'http_code' properties.
    """
    message = "An unknown exception occurred"
    http_code = 500

    def __init__(self, message=None):
        if message is not None:
            self.message = message

        super(MistralException, self).__init__(
            '%d: %s' % (self.http_code, self.message))

    @property
    def code(self):
        """This is here for webob to read.

        https://github.com/Pylons/webob/blob/master/webob/exc.py
        """
        return self.http_code

    def __str__(self):
        return self.message


# Database errors.

class DBError(MistralError):
    http_code = 400


class DBDuplicateEntryError(DBError):
    http_code = 409
    message = "Database object already exists"


class DBQueryEntryError(DBError):
    http_code = 400


class DBEntityNotFoundError(DBError):
    http_code = 404
    message = "Object not found"


# DSL exceptions.

class DSLParsingException(MistralException):
    http_code = 400


class YaqlGrammarException(DSLParsingException):
    http_code = 400
    message = "Invalid grammar of YAQL expression"


class InvalidModelException(DSLParsingException):
    http_code = 400
    message = "Wrong entity definition"


# Various common exceptions and errors.

class YaqlEvaluationException(MistralException):
    http_code = 400
    message = "Can not evaluate YAQL expression"


class DataAccessException(MistralException):
    http_code = 400


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


class EventTriggerException(MistralException):
    http_code = 400


class InputException(MistralException):
    http_code = 400


class ApplicationContextNotFoundException(MistralException):
    http_code = 400
    message = "Application context not found"


class InvalidResultException(MistralException):
    http_code = 400
    message = "Unable to parse result"


class SizeLimitExceededException(MistralException):
    http_code = 400

    def __init__(self, field_name, size_kb, size_limit_kb):
        super(SizeLimitExceededException, self).__init__(
            "Size of '%s' is %dKB which exceeds the limit of %dKB"
            % (field_name, size_kb, size_limit_kb))


class CoordinationException(MistralException):
    http_code = 500


class NotAllowedException(MistralException):
    http_code = 403
    message = "Operation not allowed"


class UnauthorizedException(MistralException):
    http_code = 401
    message = "Unauthorized"


class KombuException(Exception):
    def __init__(self, e):
        super(KombuException, self).__init__(e)

        self.exc_type = e.__class__.__name__
        self.value = str(e)
