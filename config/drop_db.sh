#!/bin/sh
set -e

envsubst < "$CONFIGS_HOME/oob_mistral_temp.conf" > "$CONFIG"

echo "Trying to drop Mistral DB"
mistral-db-nc-manage --config-file "$CONFIG" drop_db
