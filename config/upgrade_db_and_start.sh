#!/bin/bash

set -e
attempts=0
MISTRAL_TLS_ENABLED="${MISTRAL_TLS_ENABLED:-false}"
RABBITMQ_TLS_ENABLED="${RABBITMQ_TLS_ENABLED:-false}"

while [ "$attempts" -le 30 ]
do
  if { [ "$MISTRAL_TLS_ENABLED" = "true" ] || [ "$MISTRAL_TLS_ENABLED" = "True" ]; } \
   && { [ "$RABBITMQ_TLS_ENABLED" = "true" ] || [ "$RABBITMQ_TLS_ENABLED" = "True" ]; }; then
    HTTP_CODE=$(curl -k -LI -u "$RABBIT_ADMIN_USER:$RABBIT_ADMIN_PASSWORD" \
        -X GET "https://$RABBIT_HOST:15671/api/overview" \
        -o /dev/null -w '%{http_code}\n' -s)
  else
    HTTP_CODE=$(curl -LI -u "$RABBIT_ADMIN_USER:$RABBIT_ADMIN_PASSWORD" \
        -X GET "http://$RABBIT_HOST:15672/api/overview" \
        -o /dev/null -w '%{http_code}\n' -s)
  fi
   
  if [ "$HTTP_CODE" == "200" ]; then
    break;
  fi
  echo Waiting RabbitMQ start
  sleep 10
  attempts=$(( attempts + 1 ))
done

bash ./upgrade_db.sh

exec ./start.sh
