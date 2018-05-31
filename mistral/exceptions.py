# Copyright 2013 - Mirantis, Inc.
# Copyright 2015 - StackStorm, Inc.
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


class MistralFailuresBase(Exception):
    """Base class for mistral errors and exceptions"""

    message = "An unknow failure occured"

    http_code = 500

    def __init__(self, message=None):
        if message is not None:
            self.message = message

        super(MistralFailuresBase, self).__init__(
            '%d: %s' % (self.http_code, self.message))

    @property
    def code(self):
        """This is here for webob to read.

        https://github.com/Pylons/webob/blob/master/webob/exc.py
        """
        return self.http_code

    def __str__(self):
        return self.message


class MistralError(MistralFailuresBase):
    """Mistral specific error.

    Reserved for situations that can't be automatically handled. When it occurs
    it signals that there is a major environmental problem like invalid startup
    configuration or implementation problem (e.g. some code doesn't take care
    of certain corner cases). From architectural perspective it's pointless to
    try to handle this type of problems except doing some finalization work
    like transaction rollback, deleting temporary files etc.
    """

    message = "An unknown error occurred"


class MistralException(MistralFailuresBase):
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


# Database errors.

class DBError(MistralError):
    http_code = 400


class DBDuplicateEntryError(DBError):
    http_code = 409
    message = "Database object already exists"


class DBEntityNotFoundError(DBError):
    http_code = 404
    message = "Object not found"


# DSL exceptions.

class DSLParsingException(MistralException):
    http_code = 400


class ExpressionGrammarException(DSLParsingException):
    http_code = 400


class JinjaGrammarException(ExpressionGrammarException):
    message = "Invalid grammar of Jinja expression"


class YaqlGrammarException(ExpressionGrammarException):
    message = "Invalid grammar of YAQL expression"


class InvalidModelException(DSLParsingException):
    http_code = 400
    message = "Wrong entity definition"


# Various common exceptions and errors.

class EvaluationException(MistralException):
    http_code = 400


class JinjaEvaluationException(EvaluationException):
    message = "Can not evaluate Jinja expression"


class YaqlEvaluationException(EvaluationException):
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


class InvalidStateTransitionException(MistralException):
    http_code = 400
    message = 'Invalid state transition'
