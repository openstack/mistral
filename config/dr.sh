#!/usr/bin/env bash
set -e

envsubst < "$CONFIGS_HOME/oob_mistral_temp.conf" > "$CONFIG"

mistral-db-nc-manage --config-file "$CONFIG" dr