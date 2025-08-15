# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import json
import queue
import threading
import time

import aiohttp
from tornado import web

from thread_logger import BackgroundLogger

logger = BackgroundLogger()


class SyncHandler(web.RequestHandler):

    def get(self):
        logger.debug('Handle sync query')
        self.write("Hello, world")


class EchoHandler(web.RequestHandler):

    async def get(self):
        logger.debug('Handle echo query')

        await asyncio.sleep(0.5)

        self.write(self.request.body)


class AsyncHandler(web.RequestHandler):

    def initialize(self, id_queue, queue):
        self._id_queue = id_queue
        self._queue = queue

    def get(self):
        action_ex_id = self.request.headers['Mistral-Action-Execution-Id']
        self._id_queue.put(action_ex_id)
        self._queue.put(action_ex_id)

        # trace_id = self._headers.get('X-B3-TraceId')
        # if trace_id:
        #     self._queue.put(trace_id)

        logger.debug(f"Get async request with action execution id "
                     f"{action_ex_id}")

        self.write("Hello, world")


class HA_AsyncHandler(web.RequestHandler):

    def initialize(self, mistral_url):
        self._mistral_url = mistral_url
        self._body = self.request.body

    def get(self):
        action_ex_id = self.request.headers['Mistral-Action-Execution-Id']

        logger.debug(f"Get async request with action execution id "
                     f"{action_ex_id}")

        asyncio.run_coroutine_threadsafe(self._continue_action(self._mistral_url,
                                                               action_ex_id,
                                                               self._body),
                                         asyncio.get_event_loop())

        self.write("Hello, world")

    async def _continue_action(self, mistral_url, action_ex_id, task_name):
        await asyncio.sleep(1)

        body = {
            "state": 'SUCCESS',
            'output': {
                'content': task_name.decode('utf-8')
            }
        }

        async def request():
            async with aiohttp.ClientSession() as session:
                async with session.put(mistral_url + '/action_executions/' + action_ex_id,
                                       json=body) as response:
                    return response.status < 300

        for _ in range(12 * 2):
            try:
                if await request():
                    return
            except BaseException as b:
                logger.error(b)

            await asyncio.sleep(5)


class Oauth2Handler(web.RequestHandler):

    def initialize(self, queue):
        self._queue = queue
        self._headers = self.request.headers

    def _handler(self):
        token = self._headers.get('Authorization')
        if token:
            self._queue.put(token)

        logger.debug(f"Get async request with action execution id token ${token}")

        self.write("Hello, world")

    def get(self):
        self._handler()

    def post(self):
        self._handler()


class AsyncOauth2Handler(web.RequestHandler):

    def initialize(self, queue):
        self._queue = queue
        self._headers = self.request.headers

    def _handler(self):
        action_ex_id = self._headers.get('Mistral-Action-Execution-Id')
        if action_ex_id:
            self._queue.put(action_ex_id)

        # TODO: race conditions
        # token = self._headers.get('Authorization')
        # if token:
        #     self._queue.put(token)
        #
        # logger.debug(f"Get async request with action execution id "
        #              f"{action_ex_id} and token ${token}")

        self.write("Hello, world")

    def get(self):
        self._handler()

    def post(self):
        self._handler()


class WfNotifyHandler(web.RequestHandler):

    def initialize(self, status_queue, queue):
        self._status_queue = status_queue
        self._queue = queue
        self._data = json.loads(self.request.body)
        self._headers = self.request.headers

    def post(self):
        logger.debug(self._data)
        self._status_queue.put(self._data['state'])
        self._queue.put(self._data['state'])

        # trace_id = self._headers.get('X-B3-TraceId')
        # if trace_id:
        #     self._queue.put(trace_id)

        self.write("Hello, world")


class WfRetryNotifyHandler(web.RequestHandler):

    def initialize(self, queue, is_fail):
        self._queue = queue
        self._data = json.loads(self.request.body)
        self._is_fail = is_fail

    def post(self):
        logger.debug(self._data)

        if self._is_fail():
            self._queue.put('error')

            self.send_error()
            return

        self._queue.put(self._data['state'])

        self.write("Hello, world")


class TaskNotifyHandler(web.RequestHandler):

    def initialize(self, queue):
        self._queue = queue
        self._data = json.loads(self.request.body)

    def post(self):
        logger.debug(self._data)
        self._queue.put({self._data['name']: self._data['state']})

        self.write("Hello, world")


class HttpServerLibrary(object):
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'

    def __init__(self, mistral_url):
        self._mistral_url = mistral_url

        self.id_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.queue = queue.PriorityQueue()
        self._thread = threading.Thread(target=self._start_server)

        self._thread.setDaemon(True)
        self.launch_server()
        self._counter = 0
        self._fail_number = 2

    def _start_server(self):
        handlers = [(r"/sync", SyncHandler),
                    (r'/echo', EchoHandler),
                    (r'/async', AsyncHandler, {"id_queue": self.id_queue, "queue": self.queue}),
                    (r'/ha_async', HA_AsyncHandler, {"mistral_url": self._mistral_url}),
                    (r'/oauth2', Oauth2Handler, {"queue": self.queue}),
                    (r'/async_oauth2', AsyncOauth2Handler, {"queue": self.queue}),
                    (r'/wf_notify', WfNotifyHandler, {"status_queue": self.status_queue, "queue": self.queue}),
                    (r'/wf_retry_notify', WfRetryNotifyHandler, {
                        "queue": self.queue,
                        "is_fail": self.is_fail
                    }),
                    (r'/task_notify', TaskNotifyHandler, {"queue": self.queue})]

        self._app = web.Application(handlers=handlers)
        self._loop = asyncio.new_event_loop()

        asyncio.set_event_loop(self._loop)

        self._app.listen(8080)
        self._loop.run_forever()

    def launch_server(self):
        self._thread.start()

    def await_action_id(self, timeout=30):
        return self.id_queue.get(timeout=timeout)

    def await_status(self, timeout=30):
        return self.status_queue.get(timeout=timeout)

    def await_rest(self, timeout=30):
        return self.queue.get(timeout=timeout)

    def await_no_rest(self, timeout=30):
        try:
            self.queue.get(timeout=timeout)
        except queue.Empty:
            return True

        return False

    def clear_events(self):
        self._counter = 0
        self._fail_number = 2

        for q in [self.queue, self.id_queue, self.status_queue]:
            while not q.empty():
                q.get(block=False)

        logger.log_background_messages()

    def set_fail_number(self, number):
        self._fail_number = number

    def is_fail(self):
        is_fail = self._counter < self._fail_number
        self._counter += 1

        return is_fail

    def stop_server(self):
        self._loop.stop()
        self._thread.join(timeout=10)


if __name__ == '__main__':
    server_example = HttpServerLibrary('http://localhost:8989/v2')

    import requests as r

    res = r.get('http://localhost:8080/sync')
    print(res.status_code, res.text)
    time.sleep(50000000)
    server_example.stop_server()
