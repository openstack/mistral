# ``stack.sh`` calls the entry points in this order:
#
# install_mistral
# install_python_mistralclient
# configure_mistral
# start_mistral
# stop_mistral
# cleanup_mistral

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

# Defaults
# --------

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

    MISTRAL_POLICY_FILE=$MISTRAL_CONF_DIR/policy.json
    cp $MISTRAL_DIR/etc/policy.json $MISTRAL_POLICY_FILE

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
    iniset $MISTRAL_CONF_FILE oslo_messaging_rabbit rabbit_userid $RABBIT_USERID
    iniset $MISTRAL_CONF_FILE oslo_messaging_rabbit rabbit_password $RABBIT_PASSWORD

    # Configure the database.
    iniset $MISTRAL_CONF_FILE database connection `database_connection_url mistral`
    iniset $MISTRAL_CONF_FILE database max_overflow -1
    iniset $MISTRAL_CONF_FILE database max_pool_size 1000

    # Configure action execution deletion policy
    iniset $MISTRAL_CONF_FILE api allow_action_execution_deletion True

    # Path of policy.json file.
    iniset $MISTRAL_CONF oslo_policy policy_file $MISTRAL_POLICY_FILE

    if [ "$LOG_COLOR" == "True" ] && [ "$SYSLOG" == "False" ]; then
        setup_colorized_logging $MISTRAL_CONF_FILE DEFAULT tenant user
    fi

    if [ "$MISTRAL_RPC_IMPLEMENTATION" ]; then
        iniset $MISTRAL_CONF_FILE DEFAULT rpc_implementation $MISTRAL_RPC_IMPLEMENTATION
    fi
}


# init_mistral - Initialize the database
function init_mistral {
    # (re)create Mistral database
    recreate_database mistral utf8
    python $MISTRAL_DIR/tools/sync_db.py --config-file $MISTRAL_CONF_FILE
}


# install_mistral - Collect source and prepare
function install_mistral {
    setup_develop $MISTRAL_DIR

    # installing python-nose.
    real_install_package python-nose

    if is_service_enabled horizon; then
        _install_mistraldashboard
    fi
}


function _install_mistraldashboard {
    git_clone $MISTRAL_DASHBOARD_REPO $MISTRAL_DASHBOARD_DIR $MISTRAL_DASHBOARD_BRANCH
    setup_develop $MISTRAL_DASHBOARD_DIR
    ln -fs $MISTRAL_DASHBOARD_DIR/_50_mistral.py.example $HORIZON_DIR/openstack_dashboard/local/enabled/_50_mistral.py
}


function install_mistral_pythonclient {
    if use_library_from_git "python-mistralclient"; then
        git_clone $MISTRAL_PYTHONCLIENT_REPO $MISTRAL_PYTHONCLIENT_DIR $MISTRAL_PYTHONCLIENT_BRANCH
        local tags=`git --git-dir=$MISTRAL_PYTHONCLIENT_DIR/.git tag -l | grep 2015`
        if [ ! "$tags" = "" ]; then
            git --git-dir=$MISTRAL_PYTHONCLIENT_DIR/.git tag -d $tags
        fi
        setup_develop $MISTRAL_PYTHONCLIENT_DIR
    fi
}


# start_mistral - Start running processes, including screen
function start_mistral {
    if is_service_enabled mistral-api && is_service_enabled mistral-engine && is_service_enabled mistral-executor && is_service_enabled mistral-event-engine ; then
        echo_summary "Installing all mistral services in separate processes"
        run_process mistral-api "$MISTRAL_BIN_DIR/mistral-server --server api --config-file $MISTRAL_CONF_DIR/mistral.conf"
        run_process mistral-engine "$MISTRAL_BIN_DIR/mistral-server --server engine --config-file $MISTRAL_CONF_DIR/mistral.conf"
        run_process mistral-executor "$MISTRAL_BIN_DIR/mistral-server --server executor --config-file $MISTRAL_CONF_DIR/mistral.conf"
        run_process mistral-event-engine "$MISTRAL_BIN_DIR/mistral-server --server event-engine --config-file $MISTRAL_CONF_DIR/mistral.conf"
    else
        echo_summary "Installing all mistral services in one process"
        run_process mistral "$MISTRAL_BIN_DIR/mistral-server --server all --config-file $MISTRAL_CONF_DIR/mistral.conf"
    fi
}


# stop_mistral - Stop running processes
function stop_mistral {
    # Kill the Mistral screen windows
    for serv in mistral mistral-api mistral-engine mistral-executor mistral-event-engine; do
        stop_process $serv
    done
}


function cleanup_mistral {
    if is_service_enabled horizon; then
        _mistral_cleanup_mistraldashboard
    fi
}


function _mistral_cleanup_mistraldashboard {
    rm -f $HORIZON_DIR/openstack_dashboard/local/enabled/_50_mistral.py
}


if is_service_enabled mistral; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing mistral"
        install_mistral
        install_mistral_pythonclient
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
        echo_summary "Shutting down mistral"
        stop_mistral
    fi

    if [[ "$1" == "clean" ]]; then
        echo_summary "Cleaning mistral"
        cleanup_mistral
    fi
fi


# Restore xtrace
$XTRACE

# Local variables:
# mode: shell-script
# End:
