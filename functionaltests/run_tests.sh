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

if ! timeout ${API_RESPONDING_TIMEOUT} sh -c "while ! curl -s http://127.0.0.1:8989/v2/ 2>/dev/null | grep -q 'Authentication required' ; do sleep 1; done"; then
    echo "Mistral API failed to respond within ${API_RESPONDING_TIMEOUT} seconds"
    exit 1
fi

echo "Successfully contacted Mistral API"

# Where tempest code lives
TEMPEST_DIR=${TEMPEST_DIR:-/opt/stack/new/tempest}

# Where mistral code and mistralclient code live
MISTRAL_DIR=/opt/stack/new/mistral
MISTRALCLIENT_DIR=/opt/stack/new/python-mistralclient

# Define PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$TEMPEST_DIR

#installing requirements for tempest
pip install -r $TEMPEST_DIR/requirements.txt

pwd
nosetests -sv mistral/tests/functional/
