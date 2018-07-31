#!/bin/bash
set -e

# If a Mistral config doesn't exist we should create it and fill in with
# parameters
if [ ! -f ${CONFIG_FILE} ]; then
    oslo-config-generator \
      --config-file "${MISTRAL_DIR}/tools/config/config-generator.mistral.conf" \
      --output-file "${CONFIG_FILE}"

    ${INI_SET} DEFAULT js_implementation py_mini_racer
    ${INI_SET} oslo_policy policy_file "${MISTRAL_DIR}/etc/policy.json"

    ${INI_SET} DEFAULT auth_type ${AUTH_TYPE}
    ${INI_SET} pecan auth_enable ${AUTH_ENABLE}
    ${INI_SET} keycloak_oidc auth_url ${AUTH_URL}
    ${INI_SET} keycloak_oidc insecure true

    ${INI_SET} DEFAULT transport_url "${MESSAGE_BROKER_URL}"
    ${INI_SET} database connection "${DATABASE_URL}"
    ${INI_SET} DEFAULT debug "${LOG_DEBUG}"
fi

if [ ${DATABASE_URL} == "sqlite:///mistral.db" -a ! -f ./mistral.db ]
then
    python ./tools/sync_db.py --config-file "${CONFIG_FILE}"
    mistral-db-manage --config-file "${CONFIG_FILE}" populate
fi

if "${UPGRADE_DB}";
then
    /usr/local/bin/mistral-db-manage --config-file "${CONFIG_FILE}" upgrade head
    mistral-db-manage --config-file "${CONFIG_FILE}" populate
fi
if "${RUN_TESTS}";
then
    cp "${CONFIG_FILE}" .mistral.conf
    "${MISTRAL_DIR}/run_tests.sh" -N
else
    mistral-server --config-file "${CONFIG_FILE}" --server ${MISTRAL_SERVER}
fi
