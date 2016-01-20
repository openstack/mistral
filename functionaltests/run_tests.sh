#!/bin/bash
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# How many seconds to wait for the API to be responding before giving up
API_RESPONDING_TIMEOUT=20

if ! timeout ${API_RESPONDING_TIMEOUT} sh -c "until curl --output /dev/null --silent --head --fail http://localhost:8989; do sleep 1; done"; then
    echo "Mistral API failed to respond within ${API_RESPONDING_TIMEOUT} seconds"
    exit 1
fi

echo "Successfully contacted Mistral API"

# Where tempest code lives
TEMPEST_DIR=${TEMPEST_DIR:-/opt/stack/new/tempest}

# Path to directory with tempest.conf file, otherwise it will
# take relative path from where the run tests command is being executed.
export TEMPEST_CONFIG_DIR=${TEMPEST_CONFIG_DIR:-$TEMPEST_DIR/etc/}
echo "Tempest configuration file directory: $TEMPEST_CONFIG_DIR"

# Where mistral code and mistralclient code live
MISTRAL_DIR=/opt/stack/new/mistral
MISTRALCLIENT_DIR=/opt/stack/new/python-mistralclient

# Define PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$TEMPEST_DIR

pwd
nosetests -sv mistral_tempest_tests/tests/
