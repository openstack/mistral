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

set -ex

sudo chmod -R a+rw /opt/stack/
(cd $BASE/new/tempest/; sudo virtualenv .venv)
source $BASE/new/tempest/.venv/bin/activate

(cd $BASE/new/tempest/; sudo pip install -r requirements.txt -r test-requirements.txt)
sudo pip install nose
sudo pip install numpy

sudo cp $BASE/new/tempest/etc/logging.conf.sample $BASE/new/tempest/etc/logging.conf

(cd $BASE/new/mistral/; sudo pip install -r requirements.txt -r test-requirements.txt)
(cd $BASE/new/mistral/; sudo python setup.py install)

export TOX_TESTENV_PASSENV=ZUUL_PROJECT
(cd $BASE/new/tempest/; sudo -E testr init)
(cd $BASE/new/tempest/; sudo -E tox -eall-plugin mistral)