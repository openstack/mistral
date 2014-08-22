#!/bin/sh

tox -evenv -- python tools/sync_db.py "$@"