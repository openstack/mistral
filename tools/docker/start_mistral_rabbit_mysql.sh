#! /bin/bash -e

if [ "${1}" == "--help" ]; then
    echo '
    Synopsis:

       start_mistral_rabbit_mysql.sh [single|multi|clean]

    Environment variables:

    EXTRA_OPTS : extra parameters to be used for all mistral containers (e.g. -v)
    MYSQL_ROOT_PASSWORD : password for the MySQL server
    SCRATCH : remove all existing containers (RabbitMQ and MySQL are not removed by default)
    '
    exit 0
fi

MODE=${1:-single}

export MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD:-strangehat}

MISTRAL_CONTAINERS=$(docker ps -a --format '{{.ID}} {{.Names}}' | grep mistral || true)

if [ -z "$SCRATCH" -a "$MODE" != 'clean' ]; then
    MISTRAL_CONTAINERS=$(echo "$MISTRAL_CONTAINERS" | grep -v rabbitmq | grep -v mysql | cat)
fi

if [ -n "$MISTRAL_CONTAINERS" ]; then
    echo "Removing existing containers: $MISTRAL_CONTAINERS"
    KILLED_CONTAINERS=$(echo "$MISTRAL_CONTAINERS" | awk '{print $1}')
    docker kill -s 9 $KILLED_CONTAINERS
    docker rm $KILLED_CONTAINERS
fi

if [ "$MODE" == 'clean' ]; then
    echo "Clean complete"
    exit 0
fi

if [ -z "$(docker ps -aq --filter "Name=mistral-mysql")" ]; then
    docker create --name mistral-mysql -e MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD} mysql
fi
docker start mistral-mysql
if [ -z "$(docker ps -aq --filter "Name=mistral-rabbitmq")" ]; then
    docker create --name mistral-rabbitmq rabbitmq
fi
docker start mistral-rabbitmq

while true; do
  sleep 5
  docker exec mistral-mysql \
    mysql -u root -pstrangehat \
    -e "CREATE DATABASE IF NOT EXISTS mistral;
        USE mistral;
        GRANT ALL ON mistral.* TO 'root'@'%' IDENTIFIED BY '${MYSQL_ROOT_PASSWORD}'" \
  && break || true
done

sleep 10

docker run -dit --link mistral-mysql:mysql --name mistral-db-setup mistral-all cat
docker exec mistral-db-setup python /opt/stack/mistral/tools/sync_db.py
docker kill -s 9 mistral-db-setup
docker rm mistral-db-setup

function run_mistral() {
    NAME=${1:-mistral}
    shift || true
    LINKS='--link mistral-mysql:mysql --link mistral-rabbitmq:rabbitmq'
    docker run \
            -d \
            --name $NAME \
	        $LINKS \
	        ${EXTRA_OPTS} \
            ${OPTS} \
            mistral-all "$@"
}

unset OPTS

case "$MODE" in

single)
    # Single node setup
    # The CMD of the mistral-all image runs the `mistral-server --server all` command.
    OPTS="-p 8989:8989" run_mistral

    echo "
    Enter the container:
      docker exec -it mistral bash

    List workflows
      docker exec mistral mistral workflow-list

    "
    ;;

multi)
    # Multinode setup
    OPTS="-p 8989:8989" run_mistral "mistral-api" mistral-server --server api
    run_mistral "mistral-engine" mistral-server --server engine
    run_mistral "mistral-executor-1" mistral-server --server executor
    run_mistral "mistral-executor-2" mistral-server --server executor

    echo "
    List workflows
      docker exec mistral-api mistral workflow-list
    "
    ;;
esac

