FROM krallin/ubuntu-tini:16.04

LABEL name="Mistral" \
      description="Workflow Service for OpenStack" \
      maintainers="Andras Kovi <akovi@nokia.com> \
                   Vitalii Solodilov <mcdkr@yandex.ru>"

RUN apt-get -qq update && \
    apt-get install -y  \
      libffi-dev \
      libpq-dev \
      libssl-dev \
      libxml2-dev \
      libxslt1-dev \
      libyaml-dev \
      libmysqlclient-dev \
      python \
      python-dev \
      crudini \
      curl \
      git \
      gcc \
      libuv1 \
      libuv1-dev && \
      curl -f -o /tmp/get-pip.py https://bootstrap.pypa.io/3.2/get-pip.py && \
      python /tmp/get-pip.py && rm /tmp/get-pip.py && \
      pip install --upgrade pip

RUN pip install pymysql psycopg2 py_mini_racer

ENV MISTRAL_DIR="/opt/stack/mistral" \
    TMP_CONSTRAINTS="/tmp/upper-constraints.txt" \
    CONFIG_FILE="/etc/mistral/mistral.conf" \
    INI_SET="crudini --set /etc/mistral/mistral.conf" \
    MESSAGE_BROKER_URL="rabbit://guest:guest@rabbitmq:5672/" \
    DATABASE_URL="sqlite:///mistral.db" \
    UPGRADE_DB="false" \
    RUN_TESTS="false" \
    DEBIAN_FRONTEND="noninteractive" \
    MISTRAL_SERVER="all" \
    LOG_DEBUG="false" \
    AUTH_URL="http://keycloak:8080/auth" \
    AUTH_ENABLE="false" \
    AUTH_TYPE="keycloak-oidc"

# We install dependencies separatly for a caching purpose
COPY requirements.txt "${MISTRAL_DIR}/"
RUN curl -o "${TMP_CONSTRAINTS}" \
    http://git.openstack.org/cgit/openstack/requirements/plain/upper-constraints.txt && \
    sed -i "/^mistral.*/d" "${TMP_CONSTRAINTS}" && \
    pip install -r "${MISTRAL_DIR}/requirements.txt"

ARG BUILD_TEST_DEPENDENCIES="false"
COPY test-requirements.txt "${MISTRAL_DIR}/"
RUN if ${BUILD_TEST_DEPENDENCIES} ; then \
        pip install -r "${MISTRAL_DIR}/test-requirements.txt" ; \
    fi

COPY . ${MISTRAL_DIR}

RUN pip install -e "${MISTRAL_DIR}" && \
    mkdir /etc/mistral && \
    rm -rf /var/lib/apt/lists/* && \
    find ${MISTRAL_DIR} -name "*.sh" -exec chmod +x {} \;

WORKDIR "${MISTRAL_DIR}"
EXPOSE 8989
CMD "${MISTRAL_DIR}/tools/docker/start.sh"
