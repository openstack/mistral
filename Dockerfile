FROM alpine:3.10 AS builder

WORKDIR /repo

RUN apk add --no-cache git

COPY . /repo

RUN BRANCH=$(git rev-parse --abbrev-ref HEAD) && \
    ID=$(git rev-parse HEAD) && \
    COMMIT_DATE=$(date) && \
    echo "{ \"git\": { \"branch\": \"$BRANCH\", \"id\": \"$ID\", \"time\": \"$COMMIT_DATE\" }}" > /repo/version.json

FROM python:3.10.19-alpine3.22

LABEL "maintainer"="Vadim Zelenevskii wortellen@gmail.com"

SHELL ["/bin/sh", "-c"]
ENV MISTRAL_HOME=/opt/mistral \
    CONFIGS_HOME=/opt/mistral \
    MOUNT_CONFIGS_HOME=/opt/mistral/mount_configs \
    SECURITY_PROFILE=dev \
    AUTH_ENABLE=False \
    CONFIG=/opt/mistral/mistral.conf \
    RABBIT_USER='mistral_user' \
    RABBIT_PASSWORD="" \
    RABBIT_ADMIN_USER='guest' \
    RABBIT_ADMIN_PASSWORD="" \
    RABBIT_VHOST='mistral' \
    RABBIT_HOST='rabbitmq' \
    RABBIT_PORT='5672' \
    QUEUE_NAME_PREFIX="project_name" \
    PG_USER='postgres' \
    PG_PASSWORD="" \
    PG_HOST='postgres' \
    PG_PORT='5432' \
    PG_DB_NAME='mistral' \
    SERVER='all' \
    DEBUG_LOG="False" \
    RPC_IMPLEMENTATION="oslo" \
    OS_MISTRAL_URL="http://localhost:8989/v2" \
    MONITORING_ENABLED="False" \
    MONITORING_EXECUTION_DELAY="" \
    METRIC_COLLECTION_INTERVAL="30" \
    RECOVERY_ENABLED="True" \
    RECOVERY_INTERVAL="30" \
    HANG_INTERVAL="300" \
    KAFKA_NOTIFICATIONS_ENABLED="False" \
    KAFKA_HOST="0.0.0.0" \
    KAFKA_TOPIC="mistral_notifications" \
    KAFKA_CONSUMER_GROUP_ID="notification_consumer_group" \
    KAFKA_SECURITY_ENABLED="False" \
    KAFKA_SASL_PLAIN_USERNAME="" \
    KAFKA_SASL_PLAIN_PASSWORD="" \
    SKIP_RABBIT_USER_CREATION="False" \
    MISTRAL_TLS_ENABLED="False" \
    MISTRAL_MONITORING_TLS_ENABLED="False" \
    RABBITMQ_TLS_ENABLED="False" \
    KAFKA_TLS_ENABLED="False" \
    PGSSLMODE="prefer" \
    PGSSLCERT="/opt/mistral/mount_configs/tls/tls.crt" \
    PGSSLKEY="/opt/mistral/mount_configs/tls/tls.key" \
    PGSSLROOTCERT="/opt/mistral/mount_configs/tls/ca.crt"

RUN python --version && pip --version

RUN mkdir -p "${CONFIGS_HOME}" && \
    mkdir -p "${MOUNT_CONFIGS_HOME}" && \
    mkdir -p "${MOUNT_CONFIGS_HOME}/custom"

RUN echo 'https://dl-cdn.alpinelinux.org/alpine/v3.20/main/' > /etc/apk/repositories && \
    echo 'https://dl-cdn.alpinelinux.org/alpine/v3.20/community/' >> /etc/apk/repositories

# hadolint ignore=DL3008, DL3009, DL3018
RUN apk add --no-cache \
    alpine-sdk \
    libffi-dev \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    yaml-dev \
    gettext \
    procps \
    #       crudini \
    curl \
    git \
    gcc \
    make \
    musl-dev \
    libuv \
    libuv-dev \
    librdkafka \
    librdkafka-dev \
    bash \
    postgresql-client

RUN apk update --no-cache

WORKDIR $CONFIGS_HOME

COPY --from=builder /repo/version.json /opt/mistral/version.json

COPY requirements.txt requirements.txt
COPY nc_requirements.txt nc_requirements.txt

# hadolint ignore=DL3013
RUN pip install --upgrade pip==25.2 wheel && \
    pip install -r requirements.txt && \
    pip install -r nc_requirements.txt

COPY . $MISTRAL_HOME

# hadolint ignore=SC2086, DL3013
RUN pip install --no-dependencies --no-cache-dir -e $MISTRAL_HOME && \
    cp -r $MISTRAL_HOME/config/* $CONFIGS_HOME && \
    chmod -R 777 $CONFIGS_HOME && chmod 777 $CONFIGS_HOME

# RUN pip install --upgrade pip==23.3 "setuptools==70.0.0"

RUN python -c "import uuid; print(uuid.uuid4())" > \
            /opt/mistral/mistral_version

VOLUME /opt/mistral

EXPOSE 8989 9090
USER 1005000:1005000

RUN find / -perm /6000 -type f -exec chmod a-s {} \; || true

ENTRYPOINT ["./envs.sh"]
CMD ["./start.sh"]
