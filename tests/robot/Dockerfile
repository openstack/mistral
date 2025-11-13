FROM ghcr.io/netcracker/qubership-docker-integration-tests:main

ENV ROBOT_OUTPUT=${ROBOT_HOME}/output \
    DISTR_DIR=/tmp/deps \
    SERVICE_CHECKER_SCRIPT=${ROBOT_HOME}/mistral_pods_checker.py \
    SERVICE_CHECKER_SCRIPT_TIMEOUT=500 \
    STATUS_WRITING_ENABLED=true \
    IS_SHORT_STATUS_MESSAGE=false

RUN mkdir -p ${ROBOT_OUTPUT}

COPY requirements.txt ${ROBOT_HOME}/requirements.txt
COPY mistral_pods_checker.py ${ROBOT_HOME}/mistral_pods_checker.py
COPY . ${ROBOT_HOME}

# # Add necessary packages
# RUN apk update && \
#     apk add --no-cache \
#       libffi-dev \
#       libpq-dev \
#       libressl-dev \
#       libxml2-dev \
#       libxslt-dev \
#       yaml-dev \
#       gettext \
#       procps \
#       curl \
#       git \
#       gcc \
#       make \
#       musl-dev \
#       libuv \
#       libuv-dev \
#       unzip \
#       wget \
#       bash

# Upgrade all tools to avoid vulnerabilities
RUN set -x && apk upgrade --no-cache --available

RUN set -x \
    && pip3 install --upgrade pip==25.3 wheel \
    && pip3 install -r ${ROBOT_HOME}/requirements.txt \
    && rm -rf /var/cache/apk/*

RUN chmod 777 ${ROBOT_HOME}/tests && chmod 777 ${ROBOT_OUTPUT}

USER 1000:0

# Expose the port
EXPOSE 8080
VOLUME ["${ROBOT_OUTPUT}"]
