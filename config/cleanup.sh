#!/bin/sh

### Script for cleaning up database, rabbit and kafka
set -e

echo "Start deleting database"

DB_NAME=${PG_DB_NAME}
DB_USER=${PG_ADMIN_USER}
# shellcheck disable=SC2153
DB_PASSWORD=${PG_ADMIN_PASSWORD}
DB_HOST=${PG_HOST}
DB_PORT=${PG_PORT:-5432}

export PGPASSWORD="${DB_PASSWORD}"

if psql -h "$DB_HOST" -U "$DB_USER" -p "$DB_PORT" -d postgres <<EOF
ALTER DATABASE "$DB_NAME" WITH ALLOW_CONNECTIONS = false;

SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DB_NAME'
  AND pid <> pg_backend_pid();

EOF
then
  echo "Closed existing connections to $DB_NAME."
else
  echo "Error closing existing connections to $DB_NAME."
  exit 1
fi



if psql -h "$DB_HOST" -U "$DB_USER" -p "$DB_PORT" -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"; then
  echo "Database $DB_NAME successfully deleted."
else
  echo "Error during deleting database $DB_NAME."
  exit 1
fi

echo "Start deleting RabbitMQ vhost"

response=$(curl -u "$RABBIT_ADMIN_USER:$RABBIT_ADMIN_PASSWORD" \
                -X DELETE "http://$RABBIT_HOST:15672/api/vhosts/$RABBIT_VHOST" \
                -s -o /dev/null -w "%{http_code}")

if [ "$response" -eq 204 ]; then
  echo "vhost $RABBIT_HOST successfuly deleted."
elif [ "$response" -eq 404 ]; then
  echo "Vhost $RABBIT_VHOST does not exist. Assuming it was already deleted."
else
  echo "Error during deleting vhost $RABBIT_HOST. Error code: $response"
  exit 1
fi

if [ "$KAFKA_NOTIFICATIONS_ENABLED" = "True" ]; then
  envsubst < "$CONFIGS_HOME/oob_mistral_temp.conf" > "$CONFIG"
  echo "Deleting Kafka topic..."
  mistral-db-nc-manage --config-file "$CONFIG" delete_kafka_topic || true
  echo "Topic deleted successfuly"
else
  echo "Kafka topic deletion is disabled."
fi
