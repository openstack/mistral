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

# This script is executed inside post_test_hook function in devstack gate.


RETVAL=0

#Run API tests only for mistral repository
if [[ "$ZUUL_PROJECT" == "stackforge/mistral" ]]; then
    cd /opt/stack/new/mistral/functionaltests
    sudo ./run_tests.sh
    RETVAL=$?
    # Copy tempest log files to be published among other logs upon job completion
    sudo cp /opt/stack/new/mistral/functionaltests/tempest.log /opt/stack/logs
fi

#Run client tests for both repositories: mistral and python-mistralclient
if [[ RETVAL -eq 0 ]]; then
    cd /opt/stack/new/python-mistralclient/functionaltests
    sudo ./run_tests.sh
    RETVAL=$?
fi

# Copy tempest log files to be published among other logs upon job completion
sudo cp /opt/stack/new/python-mistralclient/functionaltests/tempest.log /opt/stack/logs/tempest_client.log

exit $RETVAL
