#  Copyright 2014-2015 Nokia Networks
#  Copyright 2016- Robot Framework Foundation
# Modified in 2025 by NetCracker Technology Corp.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from __future__ import print_function, with_statement

try:
    from collections import OrderedDict
except ImportError:  # New in Python 2.7
    OrderedDict = dict
import threading
import time

from robot.api import logger

__version__ = '1.3dev'


class BaseLogger(object):
    """Base class for custom loggers with same api as ``robot.api.logger``."""

    def trace(self, msg, html=False):
        self.write(msg, 'TRACE', html)

    def debug(self, msg, html=False):
        self.write(msg, 'DEBUG', html)

    def error(self, msg, html=False):
        self.write(msg, 'ERROR', html)

    def info(self, msg, html=False, also_to_console=False):
        self.write(msg, 'INFO', html)
        if also_to_console:
            self.console(msg)

    def warn(self, msg, html=False):
        self.write(msg, 'WARN', html)

    def console(self, msg, newline=True, stream='stdout'):
        logger.console(msg, newline, stream)

    def write(self, msg, level, html=False):
        raise NotImplementedError


class BackgroundLogger(BaseLogger):
    """A logger which can be used from multiple threads.
    The messages from main thread will go to robot logging api (or Python
    logging if Robot is not running). Messages from other threads are saved
    to memory and can be later logged with ``log_background_messages()``.
    This will also remove the messages from memory.
    Example::
        from robotbackgroundlogger import BackgroundLogger
        logger = BackgroundLogger()
    After that logger can be used mostly like ``robot.api.logger`::
        logger.debug('Hello, world!')
        logger.info('<b>HTML</b> example', html=True)
    """
    LOGGING_THREADS = logger.librarylogger.LOGGING_THREADS

    def __init__(self):
        self.lock = threading.RLock()
        self._messages = OrderedDict()

    def write(self, msg, level, html=False):
        with self.lock:
            thread = threading.currentThread().getName()
            if thread in self.LOGGING_THREADS:
                logger.write(msg, level, html)
            else:
                message = BackgroundMessage(msg, level, html)
                self._messages.setdefault(thread, []).append(message)

    def log_background_messages(self, name=None):
        """Forwards messages logged on background to Robot Framework log.
        By default forwards all messages logged by all threads, but can be
        limited to a certain thread by passing thread's name as an argument.
        Logged messages are removed from the message storage.
        This method must be called from the main thread.
        """
        thread = threading.currentThread().getName()
        if thread not in self.LOGGING_THREADS:
            raise RuntimeError(
                "Logging background messages is only allowed from the main "
                "thread. Current thread name: %s" % thread)
        with self.lock:
            if name:
                self._log_messages_by_thread(name)
            else:
                self._log_all_messages()

    def _log_messages_by_thread(self, name):
        for message in self._messages.pop(name, []):
            print(message.format())

    def _log_all_messages(self):
        for thread in list(self._messages):
            # Only way to get custom timestamps currently is with print
            print("*HTML* <b>Messages by '%s'</b>" % thread)
            for message in self._messages.pop(thread):
                print(message.format())

    def reset_background_messages(self, name=None):
        with self.lock:
            if name:
                self._messages.pop(name)
            else:
                self._messages.clear()


class BackgroundMessage(object):

    def __init__(self, message, level='INFO', html=False):
        self.message = message
        self.level = level.upper()
        self.html = html
        self.timestamp = time.time() * 1000

    def format(self):
        # Can support HTML logging only with INFO level.
        html = self.html and self.level == 'INFO'
        level = self.level if not html else 'HTML'
        return "*%s:%d* %s" % (level, round(self.timestamp), self.message)