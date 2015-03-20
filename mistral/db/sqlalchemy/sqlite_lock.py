# Copyright 2015 - Mirantis, Inc.
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

from eventlet import semaphore


_mutex = semaphore.Semaphore()
_locks = {}


def acquire_lock(obj_id, session):
    with _mutex:
        if obj_id not in _locks:
            _locks[obj_id] = (session, semaphore.BoundedSemaphore(1))

        tup = _locks.get(obj_id)

    tup[1].acquire()

    # Make sure to update the dictionary once the lock is acquired
    # to adjust session ownership.
    _locks[obj_id] = (session, tup[1])


def release_locks(session):
    with _mutex:
        for obj_id, tup in _locks.items():
            if tup[0] is session:
                tup[1].release()


def get_locks():
    return _locks


def cleanup():
    with _mutex:
        # NOTE: For the sake of simplicity we assume that we remove stale locks
        # after all tests because this kind of locking can only be used with
        # sqlite database. Supporting fully dynamically allocated (and removed)
        # locks is much more complex task. If this method is not called after
        # tests it will cause a memory leak.
        _locks.clear()
