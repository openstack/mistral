# 70-mistral.sh - DevStack extras script to install Mistral

if is_service_enabled mistral; then
    if [[ "$1" == "source" ]]; then
        # Initial source
        source $TOP_DIR/lib/mistral
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
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
