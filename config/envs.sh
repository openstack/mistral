#!/bin/bash

function unset_if_empty {
    env_name="${1}"
    env_val="$(printf '%s\n' "${!env_name}")"

    if [[ -z "${env_val// }" ]] || [[ "${env_val}" = "null" ]] ;
    then
        unset "${env_name}"
    fi
}

unset_if_empty HTTP_PROXY
unset_if_empty HTTPS_PROXY
unset_if_empty NO_PROXY

ENGINE_TOPIC="${QUEUE_NAME_PREFIX}_mistral_engine"
EXECUTOR_TOPIC="${QUEUE_NAME_PREFIX}_mistral_executor"
NOTIFIER_TOPIC="${QUEUE_NAME_PREFIX}_mistral_notifier"

export ENGINE_TOPIC
export EXECUTOR_TOPIC
export NOTIFIER_TOPIC

MISTRAL_VERSION=$(cat /opt/mistral/mistral_version)
export MISTRAL_VERSION

exec "$@"