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

# By default, mistral is installed in DEVSTACK_VENV
# NOTE(arnaud) maybe check if PROJECT_VENV should be used here
MISTRAL_ENV_DIR=${DEVSTACK_VENV}

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
        "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST/workflow/v2" \
        "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST/workflow/v2" \
        "$MISTRAL_SERVICE_PROTOCOL://$MISTRAL_SERVICE_HOST/workflow/v2"
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
    configure_keystone_authtoken_middleware $MISTRAL_CONF_FILE mistral
    iniset $MISTRAL_CONF_FILE keystone_authtoken www_authenticate_uri $KEYSTONE_AUTH_URI_V3

    # Setup RabbitMQ credentials
    iniset_rpc_backend mistral $MISTRAL_CONF_FILE

    # Configure the database.
    iniset $MISTRAL_CONF_FILE database connection `database_connection_url mistral`
    iniset $MISTRAL_CONF_FILE database max_overflow -1
    iniset $MISTRAL_CONF_FILE database max_pool_size 1000

    # Configure action execution deletion policy
    iniset $MISTRAL_CONF_FILE api allow_action_execution_deletion True

    # Don't use the default 0.0.0.0 it's good only for ipv4
    iniset $MISTRAL_CONF_FILE api host $(ipv6_unquote $MISTRAL_SERVICE_HOST)

    if [ "$LOG_COLOR" == "True" ] && [ "$SYSLOG" == "False" ]; then
        setup_colorized_logging $MISTRAL_CONF_FILE DEFAULT tenant user
    fi

    write_uwsgi_config "$MISTRAL_UWSGI_CONF" "$MISTRAL_UWSGI" "/workflow" "" "mistral-api"
}


# init_mistral - Initialize the database
function init_mistral {
    # (re)create Mistral database
    recreate_database mistral utf8
    $MISTRAL_BIN_DIR/mistral-db-manage --config-file $MISTRAL_CONF_FILE upgrade head
    $MISTRAL_BIN_DIR/mistral-db-manage --config-file $MISTRAL_CONF_FILE populate
}


# install_mistral - Collect source and prepare
function install_mistral {
    setup_develop $MISTRAL_DIR

    if is_service_enabled horizon; then
        _install_mistraldashboard
    fi
}


function _install_mistraldashboard {
    git_clone $MISTRAL_DASHBOARD_REPO $MISTRAL_DASHBOARD_DIR $MISTRAL_DASHBOARD_BRANCH
    setup_develop $MISTRAL_DASHBOARD_DIR
    ln -fs $MISTRAL_DASHBOARD_DIR/mistraldashboard/enabled/_50_mistral.py $HORIZON_DIR/openstack_dashboard/local/enabled/_50_mistral.py
}


function install_mistral_pythonclient {
    if use_library_from_git "python-mistralclient"; then
        git_clone_by_name "python-mistralclient"
        setup_dev_lib "python-mistralclient"
        sudo install -D -m 0644 -o $STACK_USER {${GITDIR["python-mistralclient"]}/tools/,/etc/bash_completion.d/}mistral.bash_completion
    fi
}

function install_mistral_lib {
    if use_library_from_git "mistral-lib"; then
        git_clone $MISTRAL_LIB_REPO $MISTRAL_LIB_DIR $MISTRAL_LIB_BRANCH
        setup_develop $MISTRAL_LIB_DIR
    fi
}

function install_mistral_extra {
    if use_library_from_git "mistral-extra"; then
        git_clone $MISTRAL_EXTRA_REPO $MISTRAL_EXTRA_DIR $MISTRAL_EXTRA_BRANCH
        setup_develop $MISTRAL_EXTRA_DIR
    fi
}

# start_mistral - Start running processes
function start_mistral {
    if is_service_enabled mistral-api && is_service_enabled mistral-engine && is_service_enabled mistral-executor && is_service_enabled mistral-event-engine ; then
        echo_summary "Installing all mistral services in separate processes"
        run_process mistral-api "$(which uwsgi) --procname-prefix mistral-api --ini $MISTRAL_UWSGI_CONF"
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
    for serv in mistral mistral-api mistral-engine mistral-executor mistral-event-engine; do
        stop_process $serv
    done
}

function configure_tempest_for_mistral {
    if is_service_enabled tempest; then
        iniset $TEMPEST_CONFIG mistral_api service_api_supported True
    fi
}

function cleanup_mistral {
    if is_service_enabled horizon; then
        _mistral_cleanup_mistraldashboard
    fi
    sudo rm -rf $MISTRAL_CONF_DIR
    remove_uwsgi_config "$MISTRAL_UWSGI_CONF" "$MISTRAL_UWSGI"
}


function _mistral_cleanup_mistraldashboard {
    rm -f $HORIZON_DIR/openstack_dashboard/local/enabled/_50_mistral.py
}

if is_service_enabled mistral; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing mistral"
        install_mistral
        install_mistral_lib
        install_mistral_extra
        install_mistral_pythonclient
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring mistral"
        create_mistral_accounts
        configure_mistral
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Initializing mistral"
        init_mistral
        start_mistral
    elif [[ "$1" == "stack" && "$2" == "test-config" ]]; then
        echo_summary "Configuring Tempest for Mistral"
        configure_tempest_for_mistral
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
