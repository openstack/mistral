#!/bin/bash

set -e
attempts=0

while [ "$attempts" -le 30 ]
do
  if [ "$(curl -LI -u "$RABBIT_ADMIN_USER":"$RABBIT_ADMIN_PASSWORD" -X GET http://"$RABBIT_HOST":15672/api/overview -o /dev/null -w '%{http_code}\n' -s)" == "200" ];
  then
    break;
  fi
  echo Waiting RabbitMQ start
  sleep 10
  attempts=$(( attempts + 1 ))
done

bash ./upgrade_db.sh

exec ./start.sh