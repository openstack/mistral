#! /usr/bin/env bash

ARG=$1

function pre_hook() {
  export WITHOUT_AUTH="True"
  IS_TEMPEST=$(pip freeze | grep tempest)
  if [ -z "$IS_TEMPEST" ]
    then echo "$(tput setaf 4)No such module 'tempest' in the system. Before running this script please install 'tempest' module using : pip install git+http://github.com/openstack/tempest.git$(tput sgr 0)"
  exit 1
  fi
}

function run_tests_by_version() {
  echo "$(tput setaf 4)Running integration API and workflow execution tests for v$1$(tput sgr 0)"
  export VERSION="v$1"
  nosetests -v mistral_tempest_tests/tests/api/v$1/
  unset VERSION
}

function run_tests() {
  if [ -z "$ARG" ]
  then
    run_tests_by_version 1
    run_tests_by_version 2
  elif [ "$ARG" == "v1" ]
  then
    run_tests_by_version 1
  elif [ "$ARG" == "v2" ]
  then
    run_tests_by_version 2
  fi
}

function post_hook () {
  unset LOCAL_RUN
}

#----------main-part----------

echo "$(tput setaf 4)Preparation for tests running...$(tput sgr 0)"
pre_hook
echo "$(tput setaf 4)Running tests...$(tput sgr 0)"
run_tests

post_hook

