#!/usr/bin/env bash

# Upper constraint file contains mistral version(used by tripleo-common) pin
# that is in conflict with installing mistral from source. We should replace
# the version pin in the constraints file before applying it for from-source
# installation.

ZUUL_CLONER=/usr/zuul-env/bin/zuul-cloner
BRANCH_NAME=master
MODULE_NAME=mistral
requirements_installed=$(echo "import openstack_requirements" | python 2>/dev/null ; echo $?)

set -e

CONSTRAINTS_FILE=$1
shift

install_cmd="pip install"
if [ $CONSTRAINTS_FILE != "unconstrained" ]; then

    mydir=$(mktemp -dt "$MODULE_NAME-tox_install-XXXXXXX")
    localfile=$mydir/upper-constraints.txt
    if [[ $CONSTRAINTS_FILE != http* ]]; then
        CONSTRAINTS_FILE=file://$CONSTRAINTS_FILE
    fi
    curl $CONSTRAINTS_FILE -k -o $localfile
    install_cmd="$install_cmd -c$localfile"

    if [ $requirements_installed -eq 0 ]; then
        echo "ALREADY INSTALLED" > /tmp/tox_install.txt
        echo "Requirements already installed; using existing package"
    elif [ -x "$ZUUL_CLONER" ]; then
        export ZUUL_BRANCH=${ZUUL_BRANCH-$BRANCH}
        echo "ZUUL CLONER" > /tmp/tox_install.txt
        pushd $mydir
        $ZUUL_CLONER --cache-dir /opt/git --branch $BRANCH_NAME git://git.openstack.org openstack/requirements
        cd openstack/requirements
        $install_cmd -e .
        popd
    else
        echo "PIP HARDCODE" > /tmp/tox_install.txt
        if [ -z "$REQUIREMENTS_PIP_LOCATION" ]; then
            REQUIREMENTS_PIP_LOCATION="git+https://git.openstack.org/openstack/requirements@$BRANCH_NAME#egg=requirements"
        fi
        $install_cmd -U -e ${REQUIREMENTS_PIP_LOCATION}
    fi

    edit-constraints $localfile -- $MODULE_NAME "-e file://$PWD#egg=$MODULE_NAME"
fi

$install_cmd -U $*
exit $?
