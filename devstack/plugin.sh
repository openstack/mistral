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

# Toggle for deploying Mistral API under HTTPD + mod_wsgi
MISTRAL_USE_MOD_WSGI=${MISTRAL_USE_MOD_WSGI:-True}

MISTRAL_FILES_DIR=$MISTRAL_DIR/devstack/files

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

    get_or_create_service "mistral" "workflowv2" "Workflow Service v2"
    get_or_create_endpoint "workflowv2" \
        "$REGION_NAME" \
        "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST:$MISTRAL_SERVICE_PORT/v2" \
        "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST:$MISTRAL_SERVICE_PORT/v2" \
        "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST:$MISTRAL_SERVICE_PORT/v2"
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

    # create and clean up auth cache dir
    mkdir_chown_stack "$MISTRAL_AUTH_CACHE_DIR"
    rm -f "$MISTRAL_AUTH_CACHE_DIR"/*

    mkdir_chown_stack "$MISTRAL_CONF_DIR"

    # Generate Mistral configuration file and configure common parameters.
    oslo-config-generator --config-file $MISTRAL_DIR/tools/config/config-generator.mistral.conf --output-file $MISTRAL_CONF_FILE
    iniset $MISTRAL_CONF_FILE DEFAULT debug $MISTRAL_DEBUG

    # Run all Mistral processes as a single process
    iniset $MISTRAL_CONF_FILE DEFAULT server all

    # Mistral Configuration
    #-------------------------

    # Setup keystone_authtoken section
    configure_auth_token_middleware $MISTRAL_CONF_FILE mistral $MISTRAL_AUTH_CACHE_DIR
    iniset $MISTRAL_CONF_FILE keystone_authtoken auth_uri $KEYSTONE_AUTH_URI_V3

    # Setup RabbitMQ credentials
    iniset_rpc_backend mistral $MISTRAL_CONF_FILE

    # Configure the database.
    iniset $MISTRAL_CONF_FILE database connection `database_connection_url mistral`
    iniset $MISTRAL_CONF_FILE database max_overflow -1
    iniset $MISTRAL_CONF_FILE database max_pool_size 1000

    # Configure action execution deletion policy
    iniset $MISTRAL_CONF_FILE api allow_action_execution_deletion True

    if [ "$LOG_COLOR" == "True" ] && [ "$SYSLOG" == "False" ]; then
        setup_colorized_logging $MISTRAL_CONF_FILE DEFAULT tenant user
    fi

    if [ "$MISTRAL_RPC_IMPLEMENTATION" ]; then
        iniset $MISTRAL_CONF_FILE DEFAULT rpc_implementation $MISTRAL_RPC_IMPLEMENTATION
    fi

    if [ "$MISTRAL_USE_MOD_WSGI" == "True" ]; then
        _config_mistral_apache_wsgi
    fi
}


# init_mistral - Initialize the database
function init_mistral {
    # (re)create Mistral database
    recreate_database mistral utf8
    $PYTHON $MISTRAL_DIR/tools/sync_db.py --config-file $MISTRAL_CONF_FILE
}


# install_mistral - Collect source and prepare
function install_mistral {
    setup_develop $MISTRAL_DIR

    # installing python-nose.
    real_install_package python-nose

    if is_service_enabled horizon; then
        _install_mistraldashboard
    fi

    if [ "$MISTRAL_USE_MOD_WSGI" == "True" ]; then
        install_apache_wsgi
    fi
}


function _install_mistraldashboard {
    git_clone $MISTRAL_DASHBOARD_REPO $MISTRAL_DASHBOARD_DIR $MISTRAL_DASHBOARD_BRANCH
    setup_develop $MISTRAL_DASHBOARD_DIR
    ln -fs $MISTRAL_DASHBOARD_DIR/mistraldashboard/enabled/_50_mistral.py $HORIZON_DIR/openstack_dashboard/local/enabled/_50_mistral.py
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


# start_mistral - Start running processes
function start_mistral {
    # If the site is not enabled then we are in a grenade scenario
    local enabled_site_file
    enabled_site_file=$(apache_site_config_for mistral-api)

    if is_service_enabled mistral-api && is_service_enabled mistral-engine && is_service_enabled mistral-executor && is_service_enabled mistral-event-engine ; then
        echo_summary "Installing all mistral services in separate processes"
        if [ -f ${enabled_site_file} ] && [ "$MISTRAL_USE_MOD_WSGI" == "True" ]; then
            enable_apache_site mistral-api
            restart_apache_server
        else
            run_process mistral-api "$MISTRAL_BIN_DIR/mistral-server --server api --config-file $MISTRAL_CONF_DIR/mistral.conf"
        fi
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
    local serv
    for serv in mistral mistral-engine mistral-executor mistral-event-engine; do
        stop_process $serv
    done

    if [ "$MISTRAL_USE_MOD_WSGI" == "True" ]; then
        disable_apache_site mistral-api
        restart_apache_server
    else
        stop_process mistral-api
    fi
}


function cleanup_mistral {
    if is_service_enabled horizon; then
        _mistral_cleanup_mistraldashboard
    fi

    if [ "$MISTRAL_USE_MOD_WSGI" == "True" ]; then
        _mistral_cleanup_apache_wsgi
    fi
    sudo rm -rf $MISTRAL_CONF_DIR
}


function _mistral_cleanup_mistraldashboard {
    rm -f $HORIZON_DIR/openstack_dashboard/local/enabled/_50_mistral.py
}

function _mistral_cleanup_apache_wsgi {
    sudo rm -f $(apache_site_config_for mistral-api)
}

# _config_mistral_apache_wsgi() - Set WSGI config files for Mistral
function _config_mistral_apache_wsgi {
    local mistral_apache_conf
    mistral_apache_conf=$(apache_site_config_for mistral-api)
    local mistral_ssl=""
    local mistral_certfile=""
    local mistral_keyfile=""
    local mistral_api_port=$MISTRAL_SERVICE_PORT
    local venv_path=""

    sudo cp $MISTRAL_FILES_DIR/apache-mistral-api.template $mistral_apache_conf
    sudo sed -e "
        s|%PUBLICPORT%|$mistral_api_port|g;
        s|%APACHE_NAME%|$APACHE_NAME|g;
        s|%MISTRAL_BIN_DIR%|$MISTRAL_BIN_DIR|g;
        s|%API_WORKERS%|$API_WORKERS|g;
        s|%SSLENGINE%|$mistral_ssl|g;
        s|%SSLCERTFILE%|$mistral_certfile|g;
        s|%SSLKEYFILE%|$mistral_keyfile|g;
        s|%USER%|$STACK_USER|g;
        s|%VIRTUALENV%|$venv_path|g
    " -i $mistral_apache_conf
}

if is_service_enabled mistral; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing mistral"
        install_mistral
        install_mistral_pythonclient
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring mistral"
        create_mistral_accounts
        configure_mistral
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
