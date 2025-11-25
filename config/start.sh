#!/bin/bash

if [ -n "$CUSTOM_INIT_SCRIPT_PATH" ]
then
    bash "$CUSTOM_INIT_SCRIPT_PATH"
fi

export EXECUTOR_TYPE=${EXECUTOR_TYPE:-remote}
envsubst < "$CONFIGS_HOME/oob_mistral_temp.conf" > "$CONFIG"

CONFIG_FILES=""

if [ -s "$MOUNT_CONFIGS_HOME/custom/custom-mistral.conf" ]
then
    MISTRAL_PARAMS="--config-file ${CONFIG} --config-file ${MOUNT_CONFIGS_HOME}/custom/custom-mistral.conf"
    CONFIG_FILES="custom-mistral.conf "
else
    MISTRAL_PARAMS="--config-file ${CONFIG}"
fi

if [ -s "$MOUNT_CONFIGS_HOME/custom/custom-mistral-service.conf" ]
then
        MISTRAL_PARAMS+=" --config-file ${MOUNT_CONFIGS_HOME}/custom/custom-mistral-service.conf"
        CONFIG_FILES+="custom-mistral-service.conf"
fi

if [ "${SERVER}" = "monitoring" ]
then
    echo "Start monitoring with files: ${CONFIG_FILES}"
    read -ra MISTRAL_OPTIONS <<<"${MISTRAL_PARAMS}"
    exec mistral-monitoring "${MISTRAL_OPTIONS[@]}"
else
    read -ra MISTRAL_OPTIONS <<<"${MISTRAL_PARAMS}"
    if [ "${SERVER}" = "engine" ]
    then
        mistral-db-nc-manage "${MISTRAL_OPTIONS[@]}" prepare_kafka_if_needed || true
    fi

    echo "Start Mistral with custom configs: ${CONFIG_FILES}"
    exec mistral-server "${MISTRAL_OPTIONS[@]}"
fi
