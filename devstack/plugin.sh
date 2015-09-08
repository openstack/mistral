# Setting configuration file for Mistral services

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Defaults
# --------

# Set up default repos
MISTRAL_REPO=${MISTRAL_REPO:-${GIT_BASE}/openstack/mistral.git}
MISTRAL_BRANCH=${MISTRAL_BRANCH:-master}

MISTRAL_PYTHONCLIENT_REPO=${MISTRAL_PYTHONCLIENT_REPO:-${GIT_BASE}/openstack/python-mistralclient.git}
MISTRAL_PYTHONCLIENT_BRANCH=${MISTRAL_PYTHONCLIENT_BRANCH:-$MISTRAL_BRANCH}
MISTRAL_PYTHONCLIENT_DIR=$DEST/python-mistralclient

# Set up default directories
MISTRAL_DIR=$DEST/mistral
MISTRAL_CONF_DIR=${MISTRAL_CONF_DIR:-/etc/mistral}
MISTRAL_CONF_FILE=${MISTRAL_CONF_DIR}/mistral.conf
MISTRAL_DEBUG=${MISTRAL_DEBUG:-True}

MISTRAL_SERVICE_HOST=${MISTRAL_SERVICE_HOST:-$SERVICE_HOST}
MISTRAL_SERVICE_PORT=${MISTRAL_SERVICE_PORT:-8989}
MISTRAL_SERVICE_PROTOCOL=${MISTRAL_SERVICE_PROTOCOL:-$SERVICE_PROTOCOL}

MISTRAL_ADMIN_USER=${MISTRAL_ADMIN_USER:-mistral}

# Support entry points installation of console scripts
if [[ -d $MISTRAL_DIR/bin ]]; then
    MISTRAL_BIN_DIR=$MISTRAL_DIR/bin
else
    MISTRAL_BIN_DIR=$(get_python_exec_prefix)
fi

# create_mistral_accounts - Set up common required mistral accounts
#
# Tenant      User       Roles
# ------------------------------
# service     mistral     admin
function create_mistral_accounts {
    if ! is_service_enabled key; then
        return
    fi

    create_service_user "mistral" "admin"

    if [[ "$KEYSTONE_CATALOG_BACKEND" = 'sql' ]]; then
        get_or_create_service "mistral" "workflowv2" "Workflow Service v2"
        get_or_create_endpoint "workflowv2" \
            "$REGION_NAME" \
            "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST:$MISTRAL_SERVICE_PORT/v2" \
            "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST:$MISTRAL_SERVICE_PORT/v2" \
            "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST:$MISTRAL_SERVICE_PORT/v2"
    fi
}


function mkdir_chown_stack {
    if [[ ! -d "$1" ]]; then
        sudo mkdir -p "$1"
    fi
    sudo chown $STACK_USER "$1"
}

# Entry points
# ------------

# configure_mistral - Set config files, create data dirs, etc
function configure_mistral {
    mkdir_chown_stack "$MISTRAL_CONF_DIR"

    # Generate Mistral configuration file and configure common parameters.
    oslo-config-generator --config-file $MISTRAL_DIR/tools/config/config-generator.mistral.conf --output-file $MISTRAL_CONF_FILE
    iniset $MISTRAL_CONF_FILE DEFAULT debug $MISTRAL_DEBUG

    # Run all Mistral processes as a single process
    iniset $MISTRAL_CONF_FILE DEFAULT server all

    # Mistral Configuration
    #-------------------------

    # Setup keystone_authtoken section
    iniset $MISTRAL_CONF_FILE keystone_authtoken auth_host $KEYSTONE_AUTH_HOST
    iniset $MISTRAL_CONF_FILE keystone_authtoken auth_port $KEYSTONE_AUTH_PORT
    iniset $MISTRAL_CONF_FILE keystone_authtoken auth_protocol $KEYSTONE_AUTH_PROTOCOL
    iniset $MISTRAL_CONF_FILE keystone_authtoken admin_tenant_name $SERVICE_TENANT_NAME
    iniset $MISTRAL_CONF_FILE keystone_authtoken admin_user $MISTRAL_ADMIN_USER
    iniset $MISTRAL_CONF_FILE keystone_authtoken admin_password $SERVICE_PASSWORD
    iniset $MISTRAL_CONF_FILE keystone_authtoken auth_uri "http://${KEYSTONE_AUTH_HOST}:5000/v3"

    # Setup RabbitMQ credentials
    iniset $MISTRAL_CONF_FILE DEFAULT rabbit_userid $RABBIT_USERID
    iniset $MISTRAL_CONF_FILE DEFAULT rabbit_password $RABBIT_PASSWORD

    # Configure the database.
    iniset $MISTRAL_CONF_FILE database connection `database_connection_url mistral`
    iniset $MISTRAL_CONF_FILE database max_overflow -1
    iniset $MISTRAL_CONF_FILE database max_pool_size 1000

    # Configure action execution deletion policy
    iniset $MISTRAL_CONF_FILE api allow_action_execution_deletion True
}


# init_mistral - Initialize the database
function init_mistral {
    # (re)create Mistral database
    recreate_database mistral utf8
    python $MISTRAL_DIR/tools/sync_db.py --config-file $MISTRAL_CONF_FILE
}


# install_mistral - Collect source and prepare
function install_mistral {
    install_mistral_pythonclient

    git_clone $MISTRAL_REPO $MISTRAL_DIR $MISTRAL_BRANCH

    # setup_package function is used because Mistral requirements
    # don't match with global-requirement.txt
    # both functions (setup_develop and setup_package) are defined at:
    # http://git.openstack.org/cgit/openstack-dev/devstack/tree/functions-common
    setup_package $MISTRAL_DIR -e

    # installing python-nose.
    real_install_package python-nose
}


function install_mistral_pythonclient {
    git_clone $MISTRAL_PYTHONCLIENT_REPO $MISTRAL_PYTHONCLIENT_DIR $MISTRAL_PYTHONCLIENT_BRANCH
    local tags=`git --git-dir=$MISTRAL_PYTHONCLIENT_DIR/.git tag -l | grep 2015`
    if [ ! "$tags" = "" ]; then
        git --git-dir=$MISTRAL_PYTHONCLIENT_DIR/.git tag -d $tags
    fi
    setup_package $MISTRAL_PYTHONCLIENT_DIR -e
}


# start_mistral - Start running processes, including screen
function start_mistral {
    screen_it mistral "cd $MISTRAL_DIR && $MISTRAL_BIN_DIR/mistral-server --config-file $MISTRAL_CONF_DIR/mistral.conf"
}


# stop_mistral - Stop running processes
function stop_mistral {
    # Kill the Mistral screen windows
    screen -S $SCREEN_NAME -p mistral -X kill
}


if is_service_enabled mistral; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing mistral"
        install_mistral
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring mistral"
        configure_mistral
        create_mistral_accounts
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Initializing mistral"
        init_mistral
        start_mistral
    fi

    if [[ "$1" == "unstack" ]]; then
        stop_mistral
    fi
fi


# Restore xtrace
$XTRACE

# Local variables:
# mode: shell-script
# End:
