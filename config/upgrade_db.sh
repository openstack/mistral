#!/bin/sh
set -e

envsubst < "$CONFIGS_HOME/oob_mistral_temp.conf" > "$CONFIG"

if [ "${MULTITENANCY_ENABLED}" = "True" ];
then
    echo "Multitenancy enabled"
else
    echo "Multitenancy disabled, upgrading Mistral DB..."

    if [ "${SKIP_RABBIT_USER_CREATION}" = "True" ];
    then
        echo "Trying to create rabbit credentials"
        mistral-db-nc-manage --config-file "$CONFIG" create_rabbit_credentials
        mistral-db-nc-manage --config-file "$CONFIG" delete_existing_queues
    fi

    mistral-db-nc-manage --config-file "$CONFIG" create_db || true
    mistral-db-nc-manage --config-file "$CONFIG" create_user || true

    CURRENT_VER=$(mistral-db-manage --config-file "$CONFIG" current) || true

    if [ "${CURRENT_VER}" = "025" ] || [ "${CURRENT_VER}" = "025 (head)" ];
    then
        CURRENT_NC_VER=$(mistral-db-nc-manage --config-file "$CONFIG" current) || true
        if [ "${CURRENT_NC_VER}" != "b99d30cf611a" ];
        then
            echo "Only upgrade from 5.2.0_nc15 and higher is supported. "
            echo "Please update your pike version and try again."
            exit 1
        fi
        echo "Upgrade Mistral's DB from pike"
        mistral-db-nc-manage --config-file "$CONFIG" set_version 024
        mistral-db-manage --config-file "$CONFIG" upgrade +1
        mistral-db-nc-manage --config-file "$CONFIG" fix_lh
        mistral-db-nc-manage --config-file "$CONFIG" set_version 026
        mistral-db-manage --config-file "$CONFIG" upgrade +4
        mistral-db-nc-manage --config-file "$CONFIG" set_version 032
        mistral-db-nc-manage --config-file "$CONFIG" set_nc_version 79ceffbdf791
    fi

    # Set idle in transaction session timeout for running queries
    mistral-db-nc-manage --config-file "$CONFIG" set_idle_timeout

    mistral-db-manage --config-file "$CONFIG" upgrade head
    mistral-db-nc-manage --config-file "$CONFIG" upgrade_db
    mistral-db-manage --config-file "$CONFIG" populate

    mistral-db-nc-manage --config-file "$CONFIG" prepare_kafka_if_needed || true

fi
